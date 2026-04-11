import logging
from datetime import timedelta
from uuid import UUID

from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.utils.timezone import now

logger = logging.getLogger(__name__)


class WorkflowEngine:

    def __init__(self) -> None:
        self.repo = WorkflowRepository()

    async def select_template(self, sharing_type: str, data_classification: str, tenant_id: int) -> dict | None:
        return await self.repo.find_template(sharing_type, data_classification, tenant_id)

    async def create_workflow_steps(self, request_id: UUID, template: dict) -> list[dict]:
        template_steps = await self.repo.find_template_steps(template["id"])
        created = []
        for ts in template_steps:
            sla_deadline = now() + timedelta(days=ts["sla_days"]) if ts["sla_days"] else None
            step = await self.repo.create_step(
                request_id=request_id,
                template_step_id=ts["id"],
                step_order=ts["step_order"],
                step_type=ts["step_type"],
                name=ts["name"],
                assignee_role=ts.get("assignee_role"),
                assignee_user_id=None,
                sla_deadline=sla_deadline,
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
            updated = await self.repo.update_step(next_step["id"], status="pending")
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
