import logging
from uuid import UUID

from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.utils.business_calendar import BusinessCalendar
from app.utils.timezone import now

logger = logging.getLogger(__name__)

# PDPL-aligned SLA caps by data classification (in business days). Mirrors
# spec v4.0 §4.4 — when a template step defines a longer SLA, the
# classification cap wins.
CLASSIFICATION_SLA_DAYS: dict[str, int] = {
    "public": 30,
    "internal": 14,
    "confidential": 7,
    "sensitive": 3,
}

# Canonical step types per spec v4.0 §4.4. Older templates may still use
# "approval" / "dpo_review" / "data_owner_approval" / "notification" — those
# fall back to assignee_role-based resolution so we don't break existing
# in-flight workflows.
STEP_TYPE_DPO = "dpo_review"
STEP_TYPE_SOURCE_DO = "source_data_owner_approval"
STEP_TYPE_RECEIVER_DO = "receiver_data_owner_confirmation"
STEP_TYPE_SOURCE_STEWARD = "source_steward_upload"
STEP_TYPE_DELIVERY = "delivery"


def _effective_sla_days(template_sla: int | None, classification: str | None) -> int | None:
    """Return the effective SLA days for a step.

    Applies the classification cap on top of the template value. If neither is
    set, returns None (no deadline).
    """
    cap = CLASSIFICATION_SLA_DAYS.get(classification) if classification else None
    if template_sla and cap:
        return min(template_sla, cap)
    return template_sla or cap


def _is_lite_workflow(request: dict | None) -> bool:
    """Spec v4.0 §4.4 'Workflow B (Lite)': public/internal classification AND
    no personal data → skip the DPO PDPL Review step.
    """
    if not request:
        return False
    classification = (request.get("data_classification") or "").lower()
    has_personal = bool(request.get("personal_data_involved"))
    return classification in ("public", "internal") and not has_personal


async def _resolve_data_owner_id(group_id: int | None) -> int | None:
    """Look up `data_owner_id` for a t_groups row. Returns None when the
    group is missing or has no DO assigned."""
    if not group_id:
        return None
    from app.platform.repositories.group_repository import GroupRepository
    group = await GroupRepository().find_by_id(group_id)
    if not group:
        return None
    return group.get("data_owner_id")


class WorkflowEngine:

    def __init__(self) -> None:
        self.repo = WorkflowRepository()

    async def select_template(self, sharing_type: str, data_classification: str, tenant_id: int) -> dict | None:
        return await self.repo.find_template(sharing_type, data_classification, tenant_id)

    async def create_workflow_steps(self, request_id: UUID, template: dict, request: dict = None) -> list[dict]:
        """Materialise per-request workflow_steps from the template.

        Implements spec v4.0 §4.4 with the project's PULL/PUSH extension.
        The mapping from "source dept" / "receiver dept" (spec terms) to
        DB columns flips depending on `request_direction`:

            PULL (default — requester asks another dept FOR data):
              spec "Source dept"   (data provider)   == DB receiver_group_id
              spec "Receiver dept" (data destination)== DB requester_group_id

            PUSH (requester SENDS data they have to another dept):
              spec "Source dept"   (data provider)   == DB requester_group_id
              spec "Receiver dept" (data destination)== DB receiver_group_id

        Skip rules:
          * Workflow B (Lite) — drop the DPO step when classification is
            public or internal AND personal_data_involved is false.
          * External shares — drop the Receiver Data Owner Confirmation
            step (no internal receiver dept exists).
          * PUSH — drop the Source Steward Upload step. The requester
            attached files (or specified the query) at create-time, so
            no separate upload step is needed.
        """
        template_steps = await self.repo.find_template_steps(template["id"])

        classification = request.get("data_classification") if request else None
        tenant_id = request.get("tenant_id") if request else None
        sharing_type = (request.get("sharing_type") if request else None) or "internal"
        direction = (request.get("request_direction") if request else None) or "pull"
        calendar = BusinessCalendar(tenant_id) if tenant_id else None
        is_lite = _is_lite_workflow(request)

        # Pick the source/receiver group id based on direction. In PULL
        # the receiver_group_id column is the spec "source"; in PUSH the
        # requester_group_id column is the spec "source". Resolve both
        # data owners up front so the per-step branch below stays simple.
        if direction == "push":
            source_group_id = request.get("requester_group_id") if request else None
            destination_group_id = request.get("receiver_group_id") if request else None
        else:
            source_group_id = request.get("receiver_group_id") if request else None
            destination_group_id = request.get("requester_group_id") if request else None

        source_do_id = await _resolve_data_owner_id(source_group_id)
        receiver_do_id = await _resolve_data_owner_id(destination_group_id)

        # Source Steward = first active 'requester' user in the SOURCE
        # group (alphabetic by email). For PULL this is a person in the
        # dept whose data is being released who can pick up the upload
        # task. PUSH skips this step entirely (the requester attached
        # the data at create-time), so we only resolve when there's
        # actually going to be such a step.
        source_steward_user_id: int | None = None
        if direction != "push" and source_group_id:
            from app.platform.repositories.user_repository import UserRepository
            steward_row = await UserRepository().find_first_in_group_by_product_role(
                source_group_id, "requester",
            )
            source_steward_user_id = steward_row["id"] if steward_row else None

        # Requester = the user who submitted this request. Same in both
        # directions: spec "Requester Steward".
        requester_user_id = request.get("requester_id") if request else None

        created: list[dict] = []
        rendered_index = 0  # step_order assigned in the actual workflow_steps table

        for ts in template_steps:
            step_type = ts.get("step_type") or ""
            assignee_role = ts.get("assignee_role")

            # ─── Skip rules per spec §4.4 + PULL/PUSH extension ──────
            if is_lite and step_type == STEP_TYPE_DPO:
                # Lite workflow: low classification + no personal data
                # → DPO review is skipped entirely.
                continue
            if sharing_type == "external" and step_type == STEP_TYPE_RECEIVER_DO:
                # External shares have no internal receiver dept to
                # confirm; skip per §4.4.
                continue
            if direction == "push" and step_type == STEP_TYPE_SOURCE_STEWARD:
                # In a PUSH the requester has already attached the file
                # (Mode A) or specified the query (Mode B) at create
                # time, so no separate "Source Steward Upload" step is
                # needed.
                continue

            # ─── Spec-aligned assignee resolution by SharingRole ─────
            # The five backend SharingRole values map cleanly to the
            # five canonical workflow steps. Resolution flips by
            # direction (see source_group_id / destination_group_id
            # above). Anything not in this match stays NULL so the
            # role-based gate in can_approve_step is the only filter.
            assignee_user_id: int | None = None
            role = (assignee_role or "").lower()
            if role == "dpo":
                # Any DPO in tenant — assignee_user_id stays null.
                assignee_user_id = None
            elif role == "data_owner":
                # Source dept's data owner: HR's DO under PULL,
                # Finance's DO under PUSH (whoever is providing data).
                assignee_user_id = source_do_id
            elif role == "receiver":
                # Receiver dept's data owner: Finance's DO under PULL
                # (the requesting dept), HR's DO under PUSH.
                assignee_user_id = receiver_do_id
            elif role == "source":
                # Source Steward — the person in the source dept who
                # prepares/uploads the data. PUSH skips this step, so
                # we only get here for PULL.
                assignee_user_id = source_steward_user_id
            elif role == "requester":
                # Requester Steward — the person who submitted the
                # request. Used by the Delivery / notification step.
                assignee_user_id = requester_user_id

            # Legacy step_type fallback (templates created before the
            # spec-aligned step_type taxonomy existed) — keep the
            # previous behaviour so old in-flight workflows don't
            # break: data_owner steps route to the source DO.
            if assignee_user_id is None and step_type == STEP_TYPE_SOURCE_DO:
                assignee_user_id = source_do_id
            elif assignee_user_id is None and step_type == STEP_TYPE_RECEIVER_DO:
                assignee_user_id = receiver_do_id

            # ─── Status, SLA ──────────────────────────────────────────
            # Only the FIRST rendered step is pending; everything after
            # waits its turn (after_skips don't change this logic).
            status = "pending" if rendered_index == 0 else "waiting"
            sla_days = _effective_sla_days(ts.get("sla_days"), classification)
            sla_deadline = None
            if sla_days and rendered_index == 0 and calendar:
                # BRD §4.3: SLA clock pauses on Saudi non-working days.
                sla_deadline = await calendar.add_business_days(now(), sla_days)

            step = await self.repo.create_step(
                request_id=request_id,
                template_step_id=ts["id"],
                step_order=rendered_index + 1,
                step_type=ts["step_type"],
                name=ts["name"],
                assignee_role=assignee_role,
                assignee_user_id=assignee_user_id,
                sla_deadline=sla_deadline,
                status=status,
            )
            created.append(step)
            rendered_index += 1

        return created

    async def advance_workflow(self, request_id: UUID, completed_step_id: UUID) -> dict | None:
        """Promote the workflow past a just-approved step.

        Walks forward from the completed step and:
          * auto-approves any `step_type='delivery'` step it encounters
            (delivery is a system/notification step — there's no human
            to click "approve"; the actual delivery side-effect, like
            minting an external pickup token + emailing the link,
            happens in the calling approve handler once advance returns
            None);
          * activates the first non-delivery step it finds by flipping
            its status from 'waiting' to 'pending' and stamping the
            SLA deadline;
          * returns None when no actionable step remains — that signals
            the caller to mark the request complete + run
            ShareFinalizationService.
        """
        steps = await self.repo.find_steps_by_request(request_id)

        completed_idx: int | None = None
        for i, step in enumerate(steps):
            if str(step["id"]) == str(completed_step_id):
                completed_idx = i
                break
        if completed_idx is None:
            return None

        # Look up SLA context once.
        req = await self.repo._fetch_row_optional(
            "SELECT data_classification, tenant_id FROM t_share_requests WHERE id = $1",
            (request_id,),
        )
        classification = req["data_classification"] if req else None
        tenant_id = req["tenant_id"] if req else None
        calendar = BusinessCalendar(tenant_id) if tenant_id else None

        # Walk forward; auto-approve delivery steps until we hit an
        # actionable step or run out.
        for j in range(completed_idx + 1, len(steps)):
            next_step = steps[j]
            if next_step.get("step_type") == STEP_TYPE_DELIVERY:
                await self.repo.update_step(
                    next_step["id"],
                    status="approved",
                    decision="approved",
                    completed_at=now(),
                )
                continue

            template_sla = None
            if next_step.get("template_step_id"):
                ts = await self.repo._fetch_row_optional(
                    "SELECT sla_days FROM t_template_steps WHERE id = $1",
                    (next_step["template_step_id"],),
                )
                if ts:
                    template_sla = ts["sla_days"]
            sla_days = _effective_sla_days(template_sla, classification)
            sla_deadline = None
            if sla_days and calendar:
                sla_deadline = await calendar.add_business_days(now(), sla_days)
            return await self.repo.update_step(
                next_step["id"], status="pending", sla_deadline=sla_deadline,
            )

        # All steps after the completed one were either auto-approved
        # delivery steps or nothing — workflow done.
        return None

    async def evaluate_conditions(self, step_template: dict, request: dict) -> bool:
        condition = step_template.get("condition_expr")
        if not condition:
            return True
        # Simple condition evaluation
        if "data_classification" in condition:
            target_class = condition.split("=")[-1].strip().strip("'\"")
            return request.get("data_classification") == target_class
        return True


def get_workflow_engine() -> WorkflowEngine:
    return WorkflowEngine()
