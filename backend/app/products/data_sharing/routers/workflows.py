from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.permissions import can_manage_workflows, require
from app.products.data_sharing.services.workflow_template_service import WorkflowTemplateService, get_workflow_template_service
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/workflows", tags=["workflows"])


class StepData(BaseModel):
    step_type: str
    name: str
    assignee_role: str | None = None
    execution_mode: str = "sequential"
    sla_days: int = 3
    condition_expr: str | None = None


class CreateTemplateBody(BaseModel):
    name: str
    sharing_type: str | None = None
    data_classification: str | None = None
    steps: list[StepData]


@router.get("/templates")
async def list_templates(
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    return await service.list_templates(auth_user.tenant_id, auth_user)


@router.post("/templates")
async def create_template(
    body: CreateTemplateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    return await service.create_template(
        auth_user.tenant_id, body.name, body.sharing_type,
        body.data_classification, [s.model_dump() for s in body.steps], auth_user,
    )


@router.get("/requests/{request_id}/steps")
async def get_request_steps(request_id: UUID, auth_user: AuthUser = Depends(get_current_user)):
    require(can_manage_workflows(auth_user), "You do not have permission to view workflow steps")
    repo = WorkflowRepository()
    return await repo.find_steps_by_request(request_id)
