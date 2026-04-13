import logging
from uuid import UUID

from app.products.data_sharing.permissions import can_manage_workflows, require
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class WorkflowTemplateService:

    def __init__(self) -> None:
        self.repo = WorkflowRepository()

    async def create_template(self, tenant_id: int, name: str, sharing_type: str | None,
                              data_classification: str | None, steps: list[dict], auth_user: AuthUser) -> dict:
        require(can_manage_workflows(auth_user), "You do not have permission to manage workflows")
        template = await self.repo.create_template(tenant_id, name, sharing_type, data_classification, auth_user.user_id)
        # Deactivate other templates with the same sharing_type + data_classification
        await self.repo.deactivate_others(tenant_id, sharing_type, data_classification, template["id"])
        for i, step_data in enumerate(steps):
            await self.repo.create_template_step(
                template_id=template["id"],
                step_order=i + 1,
                step_type=step_data["step_type"],
                name=step_data["name"],
                assignee_role=step_data.get("assignee_role"),
                execution_mode=step_data.get("execution_mode", "sequential"),
                sla_days=step_data.get("sla_days", 3),
                condition_expr=step_data.get("condition_expr"),
            )
        return template

    async def update_template(self, template_id: UUID, tenant_id: int, name: str, sharing_type: str | None,
                              data_classification: str | None, is_active: bool, steps: list[dict],
                              auth_user: AuthUser) -> dict:
        require(can_manage_workflows(auth_user), "You do not have permission to manage workflows")
        template = await self.repo.update_template(
            template_id, name=name, sharing_type=sharing_type,
            data_classification=data_classification, is_active=is_active,
        )
        if is_active:
            await self.repo.deactivate_others(tenant_id, sharing_type, data_classification, template_id)
        # Replace steps
        await self.repo.delete_template_steps(template_id)
        for i, step_data in enumerate(steps):
            await self.repo.create_template_step(
                template_id=template_id,
                step_order=i + 1,
                step_type=step_data["step_type"],
                name=step_data["name"],
                assignee_role=step_data.get("assignee_role"),
                execution_mode=step_data.get("execution_mode", "sequential"),
                sla_days=step_data.get("sla_days", 3),
                condition_expr=step_data.get("condition_expr"),
            )
        steps_list = await self.repo.find_template_steps(template_id)
        return {**template, "steps": steps_list}

    async def deactivate_template(self, template_id: UUID, auth_user: AuthUser) -> dict:
        require(can_manage_workflows(auth_user), "You do not have permission to manage workflows")
        return await self.repo.update_template(template_id, is_active=False)

    async def get_template_with_steps(self, template_id: UUID) -> dict:
        template = await self.repo._fetch_row("SELECT * FROM t_workflow_templates WHERE id = $1", (template_id,))
        steps = await self.repo.find_template_steps(template_id)
        return {**template, "steps": steps}

    async def list_templates(self, tenant_id: int, auth_user: AuthUser = None) -> list[dict]:
        if auth_user:
            require(can_manage_workflows(auth_user), "You do not have permission to manage workflows")
        return await self.repo._fetch_all(
            "SELECT * FROM t_workflow_templates WHERE tenant_id = $1 ORDER BY is_active DESC, created_at DESC",
            (tenant_id,),
        )


def get_workflow_template_service() -> WorkflowTemplateService:
    return WorkflowTemplateService()
