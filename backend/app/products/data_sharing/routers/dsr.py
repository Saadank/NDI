from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.dsr_service import DsrService, get_dsr_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/dsr", tags=["dsr"])


class CreateDsrBody(BaseModel):
    subject_name: str
    subject_email: str | None = None
    subject_id_type: str | None = None
    subject_id_value: str | None = None
    request_type: str
    description: str | None = None


class RespondDsrBody(BaseModel):
    response_summary: str


@router.get("/")
async def list_dsrs(
    auth_user: AuthUser = Depends(get_current_user),
    service: DsrService = Depends(get_dsr_service),
):
    return await service.list_dsrs(auth_user.tenant_id)


@router.post("/")
async def create_dsr(
    body: CreateDsrBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsrService = Depends(get_dsr_service),
):
    return await service.create_dsr(body.model_dump(), auth_user)


@router.get("/{dsr_id}")
async def get_dsr(
    dsr_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsrService = Depends(get_dsr_service),
):
    return await service.get_dsr(dsr_id, auth_user.tenant_id)


@router.post("/{dsr_id}/respond")
async def respond_to_dsr(
    dsr_id: UUID, body: RespondDsrBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsrService = Depends(get_dsr_service),
):
    return await service.respond_to_dsr(dsr_id, body.response_summary, auth_user)
