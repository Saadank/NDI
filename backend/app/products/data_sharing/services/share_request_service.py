import logging
from uuid import UUID

from app.platform.services.audit_service import AuditService
from app.products.data_sharing.enums.sharing_role import SharingRole
from app.products.data_sharing.permissions import (
    can_cancel_request, can_create_request, can_see_all_requests,
    can_see_assigned_requests, can_see_own_requests_only, can_see_received_requests,
    can_submit_request, can_view_request, require,
)
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.services.conflict_service import ConflictService
from app.products.data_sharing.services.external_recipient_service import ExternalRecipientService
from app.products.data_sharing.services.workflow_engine import WorkflowEngine
from app.structures.auth_user import AuthUser
from app.utils.exceptions import BaseAppException, ForbiddenException, ValidationException
from app.utils.pagination import get_pagination_data

logger = logging.getLogger(__name__)


class ShareRequestService:

    def __init__(self) -> None:
        self.repo = ShareRequestRepository()
        self.workflow_engine = WorkflowEngine()
        self.audit = AuditService()
        self.external_recipients = ExternalRecipientService()
        self.conflicts = ConflictService()

    async def create_draft(self, data: dict, auth_user: AuthUser) -> dict:
        require(can_create_request(auth_user), "Your role cannot create requests")
        tenant_id = auth_user.tenant_id
        request_number = await self.repo.next_request_number(tenant_id)

        # Validate receiver_group belongs to the same tenant
        receiver_group_id = data.get("receiver_group_id")
        if receiver_group_id:
            from app.platform.repositories.group_repository import GroupRepository
            group_repo = GroupRepository()
            group = await group_repo.find_by_id(receiver_group_id)
            if not group or group["tenant_id"] != tenant_id:
                raise ValidationException("Receiver group not found in your organization")
            # EC-01: the receiver department cannot be the requester's own department.
            if auth_user.group_id and receiver_group_id == auth_user.group_id:
                raise ValidationException(
                    "You cannot request data from your own department"
                )

        # Validate structured-data fields if this is a structured request
        data_type = data.get("data_type", "file")
        connection_id = data.get("connection_id")
        selection_mode = data.get("selection_mode")
        selected_items = data.get("selected_items")
        custom_sql = data.get("custom_sql")
        if data_type == "structured":
            if not connection_id:
                raise ValidationException("connection_id is required for structured requests")
            if selection_mode not in ("tables", "query"):
                raise ValidationException("selection_mode must be 'tables' or 'query'")
            if selection_mode == "tables" and not selected_items:
                raise ValidationException("selected_items is required when selection_mode is 'tables'")
            if selection_mode == "query" and not custom_sql:
                raise ValidationException("custom_sql is required when selection_mode is 'query'")

        # Resolve receiver target: external recipient (non-tenant) vs receiving tenant.
        sharing_type = data.get("sharing_type", "internal")
        receiving_tenant_id = data.get("receiving_tenant_id")
        external_recipient_payload = data.get("external_recipient")
        external_recipient_id: int | None = None
        external_contact_id: int | None = None
        if sharing_type == "external":
            has_tenant = receiving_tenant_id is not None
            has_external = external_recipient_payload is not None
            if has_tenant == has_external:
                raise ValidationException(
                    "External requests require exactly one of receiving_tenant_id or external_recipient"
                )
            if has_external:
                recipient, contact = await self.external_recipients.upsert_by_email(
                    tenant_id=tenant_id,
                    org_name=external_recipient_payload["org_name"],
                    contact_email=external_recipient_payload["contact_email"],
                    contact_name=external_recipient_payload.get("contact_name"),
                    phone=external_recipient_payload.get("phone"),
                    auth_user=auth_user,
                )
                external_recipient_id = recipient["id"]
                external_contact_id = contact["id"]

        request = await self.repo.create(
            tenant_id=tenant_id,
            request_number=request_number,
            title=data["title"],
            purpose=data["purpose"],
            legal_basis=data.get("legal_basis", ""),
            sharing_type=sharing_type,
            data_classification=data.get("data_classification", "internal"),
            personal_data_involved=data.get("personal_data_involved", False),
            estimated_data_subjects=data.get("estimated_data_subjects"),
            data_subject_categories=data.get("data_subject_categories"),
            source_description=data.get("source_description"),
            requester_id=auth_user.user_id,
            receiving_tenant_id=receiving_tenant_id,
            requester_group_id=auth_user.group_id,
            receiver_group_id=receiver_group_id,
            created_by=auth_user.user_id,
            dpia_confirmed=data.get("dpia_confirmed", False),
            data_type=data_type,
            connection_id=connection_id,
            selection_mode=selection_mode,
            selected_items=selected_items,
            custom_sql=custom_sql,
            external_recipient_id=external_recipient_id,
            external_contact_id=external_contact_id,
            delivery_channel=data.get("delivery_channel", "portal"),
            # Pull = ask another dept FOR data; Push = send data TO another
            # dept. The engine maps source/receiver dept assignees off this.
            request_direction=data.get("request_direction", "pull"),
        )

        await self.audit.log(
            tenant_id=tenant_id, action_type="request.created", resource_type="share_request",
            resource_id=str(request["id"]), actor_id=auth_user.user_id,
            after_state=request, request_id=request["id"],
        )
        return request

    # Fields that are PDPL-material per spec v4.0 §4.4. If any of them
    # change between submissions the DPO step is re-triggered.
    PDPL_MATERIAL_FIELDS = (
        "data_classification",
        "legal_basis",
        "personal_data_involved",
        "data_subject_categories",
        "custom_sql",
        "selected_items",
    )

    async def submit_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        tenant_id = auth_user.tenant_id
        request = await self.repo.find_by_id(request_id, tenant_id)
        require(can_submit_request(auth_user, request), "You can only submit your own requests")

        prior_status = request["status"]
        if prior_status not in ("draft", "changes_requested"):
            raise ValidationException(
                "Only draft or changes-requested requests can be submitted"
            )

        # EC-01 re-check: requester's group may have changed since draft.
        if (
            auth_user.group_id
            and request.get("receiver_group_id")
            and request["receiver_group_id"] == auth_user.group_id
        ):
            raise ValidationException(
                "You cannot request data from your own department"
            )

        # PDPL validation
        classification = request["data_classification"]
        if request["personal_data_involved"]:
            if not request.get("legal_basis"):
                raise ValidationException("Legal basis is required for personal data")
            if not request.get("estimated_data_subjects"):
                raise ValidationException("Estimated data subjects is required for personal data")
        # Confidential and sensitive classifications also require a legal basis
        if classification in ("confidential", "sensitive") and not request.get("legal_basis"):
            raise ValidationException(
                f"Legal basis is required for {classification} data"
            )
        if classification == "sensitive" and not request.get("dpia_confirmed"):
            raise ValidationException("DPIA confirmation required for sensitive data")

        # Pull + external is not a supported combination. An external
        # party can't initiate the request from outside the platform;
        # if the tenant wants to receive data from an external party,
        # they coordinate via push from the external side (handled out
        # of band) or via the pickup portal. Reject with a 422 so the
        # wizard can surface a clear message.
        direction_check = (request.get("request_direction") or "pull").lower()
        sharing_check = (request.get("sharing_type") or "internal").lower()
        if direction_check == "pull" and sharing_check == "external":
            raise BaseAppException(
                "Pull from external sources is not supported. To receive "
                "data from an external party, coordinate via push from "
                "your side or contact your DPO.",
                status_code=422,
            )

        # PUSH validation: the requester is sending data they already
        # have, so Mode A must have at least one file attached, and Mode
        # B must have a connection + selection. PULL has no such check —
        # the source steward provides the data after approval.
        direction = (request.get("request_direction") or "pull").lower()
        if direction == "push":
            data_type = request.get("data_type") or "file"
            if data_type == "file":
                from app.products.data_sharing.repositories.file_repository import FileRepository
                files = await FileRepository().find_by_request(request["id"])
                fulfilled = [
                    f for f in files
                    if f.get("status") in ("uploaded", "clean", "scanning")
                ]
                if not fulfilled:
                    raise ValidationException(
                        "Push requests must include at least one uploaded file before submission"
                    )
            else:  # structured
                if not request.get("connection_id"):
                    raise ValidationException(
                        "Push (structured) requires a database connection"
                    )
                if not request.get("selection_mode"):
                    raise ValidationException(
                        "Push (structured) requires either selected tables or a custom query"
                    )

        if prior_status == "draft":
            # First submit: create steps from the matching active template.
            template = await self.workflow_engine.select_template(
                request["sharing_type"], request["data_classification"], tenant_id
            )
            if template:
                steps = await self.workflow_engine.create_workflow_steps(
                    request_id, template, request
                )
                # BRD §2.2 role-conflict resolution: EC-02 / EC-03 / EC-04.
                await self.conflicts.resolve_step_conflicts(request, steps, auth_user)
                await self.repo.update(request_id, workflow_template_id=template["id"])
        else:
            # Re-submit after changes_requested. Spec v4.0 §4.4 — if any
            # PDPL-material field changed since the last submitted snapshot,
            # the DPO step is re-triggered automatically.
            await self._maybe_retrigger_dpo(
                request_id, request, auth_user
            )

        updated = await self.repo.update_status(request_id, "submitted", auth_user.user_id)

        # Snapshot the request state in the audit log so future resubmits
        # have something to diff against. Same shape as request rows so
        # compare-by-key works in `_maybe_retrigger_dpo`.
        await self.audit.log(
            tenant_id=tenant_id,
            action_type="request.submitted" if prior_status == "draft" else "request.resubmitted",
            resource_type="share_request",
            resource_id=str(request_id),
            actor_id=auth_user.user_id,
            request_id=request_id,
            after_state={k: updated.get(k) for k in self.PDPL_MATERIAL_FIELDS},
        )
        return updated

    async def _maybe_retrigger_dpo(self, request_id: UUID, request: dict, auth_user: AuthUser) -> None:
        """Spec v4.0 §4.4: 'If the steward changes the classification, the
        legal basis, the personal-data flag, or the data selection itself,
        the DPO step is re-triggered automatically.'

        Compares the request's current PDPL-material fields against the
        last `request.submitted` / `request.resubmitted` audit snapshot.
        If any field differs, finds the existing DPO step and resets it
        to status='pending'; resets every later step to 'waiting' so the
        workflow restarts from PDPL review.
        """
        prior = await self.audit._fetch_row_optional(
            """SELECT after_state FROM t_audit_events
               WHERE resource_type = 'share_request'
                 AND resource_id = $1
                 AND action_type IN ('request.submitted', 'request.resubmitted')
                 AND after_state IS NOT NULL
               ORDER BY created_at DESC LIMIT 1""",
            (str(request_id),),
        )
        if not prior or not prior.get("after_state"):
            # No snapshot exists yet (request was first submitted before
            # snapshotting was added). Be conservative: re-trigger DPO
            # so a stale DPO approval doesn't survive a content change.
            should_retrigger = True
            changed: list[str] = list(self.PDPL_MATERIAL_FIELDS)
        else:
            import json
            snap = prior["after_state"]
            if isinstance(snap, str):
                snap = json.loads(snap)
            changed = [
                f for f in self.PDPL_MATERIAL_FIELDS if snap.get(f) != request.get(f)
            ]
            should_retrigger = bool(changed)

        if not should_retrigger:
            return

        # Find the DPO step on this request and reset it.
        steps = await self.workflow_engine.repo.find_steps_by_request(request_id)
        dpo_step = next(
            (
                s
                for s in steps
                if (s.get("step_type") == "dpo_review")
                or (s.get("assignee_role") == "dpo")
            ),
            None,
        )
        if not dpo_step:
            return

        # Reset DPO step to pending; reset every later step to waiting.
        await self.workflow_engine.repo.update_step(
            dpo_step["id"], status="pending", completed_at=None,
            completed_by=None, decision=None,
        )
        for s in steps:
            if s["step_order"] > dpo_step["step_order"]:
                await self.workflow_engine.repo.update_step(s["id"], status="waiting")

        await self.audit.log(
            tenant_id=auth_user.tenant_id,
            action_type="step.dpo_retriggered",
            resource_type="workflow_step",
            resource_id=str(dpo_step["id"]),
            actor_id=auth_user.user_id,
            request_id=request_id,
            metadata={"spec": "v4.0_section_4.4", "changed_fields": changed},
        )

    async def get_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        request = await self.repo.find_by_id(request_id, auth_user.tenant_id)
        require(can_view_request(auth_user, request), "You do not have access to this request")
        return request

    async def list_requests(self, auth_user: AuthUser, status: str | None = None, page: int = 1, limit: int = 20) -> dict:
        tenant_id = auth_user.tenant_id

        if can_see_all_requests(auth_user):
            requests = await self.repo.find_by_tenant(tenant_id, status, page, limit)
            total = await self.repo.count_by_tenant(tenant_id, status)
        elif can_see_assigned_requests(auth_user):
            # Data owner: see requests where their step is pending + requests sent to their group (workflow done)
            requests = await self.repo.find_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, SharingRole.DATA_OWNER, status, page, limit)
            total = await self.repo.count_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, SharingRole.DATA_OWNER, status)
        elif can_see_received_requests(auth_user):
            # Receiver: own requests + requests sent to their group (workflow done)
            requests = await self.repo.find_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, None, status, page, limit)
            total = await self.repo.count_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, None, status)
        elif can_see_own_requests_only(auth_user):
            # Requester: own requests + requests sent to their group (workflow done)
            requests = await self.repo.find_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, None, status, page, limit)
            total = await self.repo.count_for_user(
                tenant_id, auth_user.user_id, auth_user.group_id, None, status)
        else:
            raise ForbiddenException("You do not have permission to list requests")

        pagination = get_pagination_data(limit, page, total)
        return {"data": requests, **pagination}

    async def cancel_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        request = await self.repo.find_by_id(request_id, auth_user.tenant_id)
        require(can_cancel_request(auth_user, request), "You can only cancel your own requests")
        if request["status"] in ("completed", "cancelled"):
            raise ValidationException("Cannot cancel a completed or already cancelled request")
        updated = await self.repo.update_status(request_id, "cancelled", auth_user.user_id)
        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="request.cancelled", resource_type="share_request",
            resource_id=str(request_id), actor_id=auth_user.user_id, request_id=request_id,
        )
        return updated


def get_share_request_service() -> ShareRequestService:
    return ShareRequestService()
