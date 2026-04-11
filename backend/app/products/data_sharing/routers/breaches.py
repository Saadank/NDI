from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.breach_service import BreachService, get_breach_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/breaches", tags=["breaches"])


class ReportBreachBody(BaseModel):
    title: str
    description: str
    severity: str = "medium"
    request_id: UUID | None = None


@router.get("/")
async def list_breaches(
    auth_user: AuthUser = Depends(get_current_user),
    service: BreachService = Depends(get_breach_service),
):
    return await service.list_breaches(auth_user.tenant_id)


@router.post("/")
async def report_breach(
    body: ReportBreachBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: BreachService = Depends(get_breach_service),
):
    return await service.report_breach(body.model_dump(), auth_user)


@router.get("/{breach_id}")
async def get_breach(
    breach_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: BreachService = Depends(get_breach_service),
):
    return await service.get_breach(breach_id, auth_user.tenant_id)


@router.post("/{breach_id}/notify-sdaia")
async def notify_sdaia(
    breach_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: BreachService = Depends(get_breach_service),
):
    return await service.mark_sdaia_notified(breach_id, auth_user)
