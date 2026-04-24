import logging
from uuid import UUID

from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.utils.business_calendar import BusinessCalendar
from app.utils.timezone import now

logger = logging.getLogger(__name__)

# PDPL-aligned SLA caps by data classification (in days). When a template step
# defines a longer SLA, the classification cap wins.
CLASSIFICATION_SLA_DAYS: dict[str, int] = {
    "public": 30,
    "internal": 14,
    "confidential": 7,
    "sensitive": 3,
}


def _effective_sla_days(template_sla: int | None, classification: str | None) -> int | None:
    """Return the effective SLA days for a step.

    Applies the classification cap on top of the template value. If neither is
    set, returns None (no deadline).
    """
    cap = CLASSIFICATION_SLA_DAYS.get(classification) if classification else None
    if template_sla and cap:
        return min(template_sla, cap)
    return template_sla or cap


class WorkflowEngine:

    def __init__(self) -> None:
        self.repo = WorkflowRepository()

    async def select_template(self, sharing_type: str, data_classification: str, tenant_id: int) -> dict | None:
        return await self.repo.find_template(sharing_type, data_classification, tenant_id)

    async def create_workflow_steps(self, request_id: UUID, template: dict, request: dict = None) -> list[dict]:
        template_steps = await self.repo.find_template_steps(template["id"])
        # Resolve the data owner for the requester's group
        data_owner_user_id = None
        if request and request.get("requester_group_id"):
            from app.platform.repositories.group_repository import GroupRepository
            group_repo = GroupRepository()
            group = await group_repo.find_by_id(request["requester_group_id"])
            if group:
                data_owner_user_id = group.get("data_owner_id")

        classification = request.get("data_classification") if request else None
        tenant_id = request.get("tenant_id") if request else None
        calendar = BusinessCalendar(tenant_id) if tenant_id else None

        created = []
        for i, ts in enumerate(template_steps):
            # Only the first step is "pending"; the rest wait their turn
            status = "pending" if i == 0 else "waiting"
            sla_days = _effective_sla_days(ts.get("sla_days"), classification)
            # BRD §4.3: SLA clock pauses on Saudi non-working days.
            sla_deadline = None
            if sla_days and i == 0 and calendar:
                sla_deadline = await calendar.add_business_days(now(), sla_days)
            # Route data_owner steps to the specific department data owner
            assignee_user_id = None
            if ts.get("assignee_role") == "data_owner" and data_owner_user_id:
                assignee_user_id = data_owner_user_id
            step = await self.repo.create_step(
                request_id=request_id,
                template_step_id=ts["id"],
                step_order=ts["step_order"],
                step_type=ts["step_type"],
                name=ts["name"],
                assignee_role=ts.get("assignee_role"),
                assignee_user_id=assignee_user_id,
                sla_deadline=sla_deadline,
                status=status,
            )
            created.append(step)
        return created

    async def advance_workflow(self, request_id: UUID, completed_step_id: UUID) -> dict | None:
        steps = await self.repo.find_steps_by_request(request_id)
        completed_step = None
        next_step = None

        for i, step in enumerate(steps):
            if str(step["id"]) == str(completed_step_id):
                completed_step = step
                if i + 1 < len(steps):
                    next_step = steps[i + 1]
                break

        if not completed_step:
            return None

        if next_step:
            # Activate next step: set pending + calculate SLA from now
            template_sla = None
            if next_step.get("template_step_id"):
                ts = await self.repo._fetch_row_optional(
                    "SELECT sla_days FROM t_template_steps WHERE id = $1", (next_step["template_step_id"],)
                )
                if ts:
                    template_sla = ts["sla_days"]
            # Apply classification cap if the parent request is available
            classification = None
            tenant_id = None
            req = await self.repo._fetch_row_optional(
                "SELECT data_classification, tenant_id FROM t_share_requests WHERE id = $1",
                (request_id,),
            )
            if req:
                classification = req["data_classification"]
                tenant_id = req["tenant_id"]
            sla_days = _effective_sla_days(template_sla, classification)
            sla_deadline = None
            if sla_days and tenant_id:
                cal = BusinessCalendar(tenant_id)
                sla_deadline = await cal.add_business_days(now(), sla_days)
            updated = await self.repo.update_step(next_step["id"], status="pending", sla_deadline=sla_deadline)
            return updated

        # All steps complete — workflow is done
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
