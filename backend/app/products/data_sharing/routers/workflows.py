from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.permissions import (
    can_approve_step, can_manage_workflows, can_view_request,
    can_view_workflows, require,
)
from app.products.data_sharing.services.workflow_template_service import WorkflowTemplateService, get_workflow_template_service
from app.products.data_sharing.services.workflow_engine import WorkflowEngine
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
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


class UpdateTemplateBody(BaseModel):
    name: str
    sharing_type: str | None = None
    data_classification: str | None = None
    is_active: bool = True
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


@router.get("/templates/{template_id}")
async def get_template(
    template_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    # Read access — DPO uses this to inspect the template during PDPL review.
    # Mutating routes (POST/PUT/DELETE) still gate on can_manage_workflows.
    require(can_view_workflows(auth_user), "You do not have permission to view workflows")
    return await service.get_template_with_steps(template_id)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    body: UpdateTemplateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    return await service.update_template(
        template_id, auth_user.tenant_id, body.name, body.sharing_type,
        body.data_classification, body.is_active, [s.model_dump() for s in body.steps], auth_user,
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    """Hard-delete a workflow template. The previous behaviour was a
    soft-deactivate (is_active=false) which left orphaned rows in the
    list view forever; the UI now expects this to remove the template
    outright. Active requests bound to it have their workflow_template_id
    nulled, but their already-created workflow_steps survive."""
    return await service.delete_template(template_id, auth_user)


@router.post("/templates/{template_id}/activate")
async def activate_template(
    template_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    """Mark a template active. Exclusive within its scope — any other active
    template sharing the same sharing_type + data_classification is
    deactivated, so only one workflow is the default at a time."""
    return await service.activate_template(template_id, auth_user.tenant_id, auth_user)


@router.post("/templates/{template_id}/deactivate")
async def deactivate_template(
    template_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: WorkflowTemplateService = Depends(get_workflow_template_service),
):
    """Mark a template inactive (no workflow is applied to new requests in
    its scope until another is activated)."""
    return await service.deactivate_template(template_id, auth_user)


class BackfillBody(BaseModel):
    request_id: UUID | None = None
    all_stuck: bool = False


@router.post("/backfill")
async def backfill_workflow(
    body: BackfillBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Find requests that have no workflow steps yet (because they were
    submitted before any active template existed for their scope) and
    attach them to the matching active template.

    Body:
      - request_id: backfill a single request, OR
      - all_stuck:  backfill every stuck request in this tenant.

    Returns: { backfilled: int, skipped: list[{request_id, reason}] }
    """
    require(can_manage_workflows(auth_user), "You do not have permission to manage workflows")

    repo = WorkflowRepository()
    request_repo = ShareRequestRepository()
    engine = WorkflowEngine()

    targets: list[dict] = []
    if body.request_id:
        request = await request_repo.find_by_id(body.request_id, auth_user.tenant_id)
        if request is None:
            return {"backfilled": 0, "skipped": [{"request_id": str(body.request_id), "reason": "not_found"}]}
        # Only backfill if there are no steps yet — never blow away an
        # already-running workflow.
        existing = await repo.find_steps_by_request(body.request_id)
        if existing:
            return {"backfilled": 0, "skipped": [{"request_id": str(body.request_id), "reason": "already_has_steps"}]}
        targets = [request]
    elif body.all_stuck:
        targets = await repo.find_stuck_requests(auth_user.tenant_id)
    else:
        return {"backfilled": 0, "skipped": []}

    backfilled = 0
    skipped: list[dict] = []
    for r in targets:
        template = await engine.select_template(
            r.get("sharing_type"), r.get("data_classification"), auth_user.tenant_id,
        )
        if not template:
            skipped.append({"request_id": str(r["id"]), "reason": "no_active_template_matches"})
            continue
        await engine.create_workflow_steps(r["id"], template, r)
        await request_repo.update(r["id"], workflow_template_id=template["id"])
        backfilled += 1

    return {"backfilled": backfilled, "skipped": skipped}


@router.get("/requests/{request_id}/steps")
async def get_request_steps(request_id: UUID, auth_user: AuthUser = Depends(get_current_user)):
    request_repo = ShareRequestRepository()
    request = await request_repo.find_by_id(request_id, auth_user.tenant_id)
    require(can_view_request(auth_user, request), "You do not have permission to view this request")

    repo = WorkflowRepository()
    steps = await repo.find_steps_by_request(request_id)
    # Annotate each step with whether the current user can act on it
    for step in steps:
        step["can_act"] = can_approve_step(auth_user, step, request)
    return steps
