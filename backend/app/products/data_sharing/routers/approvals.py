from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.approval_service import ApprovalService, get_approval_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/requests/{request_id}/steps", tags=["approvals"])


class DecisionBody(BaseModel):
    comment: str | None = None


class RejectBody(BaseModel):
    comment: str


@router.post("/{step_id}/approve")
async def approve_step(
    request_id: UUID, step_id: UUID, body: DecisionBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
):
    return await service.approve(request_id, step_id, body.comment, auth_user)


@router.post("/{step_id}/reject")
async def reject_step(
    request_id: UUID, step_id: UUID, body: RejectBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
):
    return await service.reject(request_id, step_id, body.comment, auth_user)


@router.post("/{step_id}/request-changes")
async def request_changes(
    request_id: UUID, step_id: UUID, body: RejectBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ApprovalService = Depends(get_approval_service),
):
    return await service.request_changes(request_id, step_id, body.comment, auth_user)
