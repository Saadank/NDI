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
from app.utils.exceptions import ForbiddenException, ValidationException
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
        )

        await self.audit.log(
            tenant_id=tenant_id, action_type="request.created", resource_type="share_request",
            resource_id=str(request["id"]), actor_id=auth_user.user_id,
            after_state=request, request_id=request["id"],
        )
        return request

    async def submit_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        tenant_id = auth_user.tenant_id
        request = await self.repo.find_by_id(request_id, tenant_id)
        require(can_submit_request(auth_user, request), "You can only submit your own requests")

        if request["status"] != "draft":
            raise ValidationException("Only draft requests can be submitted")

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

        # Select matching workflow template and create steps
        template = await self.workflow_engine.select_template(
            request["sharing_type"], request["data_classification"], tenant_id
        )
        if template:
            steps = await self.workflow_engine.create_workflow_steps(
                request_id, template, request
            )
            # BRD §2.2 role-conflict resolution: EC-02 / EC-03 / EC-04.
            # Runs after step creation so every assignment is inspected in a single pass.
            await self.conflicts.resolve_step_conflicts(request, steps, auth_user)
            await self.repo.update(request_id, workflow_template_id=template["id"])

        updated = await self.repo.update_status(request_id, "submitted", auth_user.user_id)

        await self.audit.log(
            tenant_id=tenant_id, action_type="request.submitted", resource_type="share_request",
            resource_id=str(request_id), actor_id=auth_user.user_id, request_id=request_id,
        )
        return updated

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
