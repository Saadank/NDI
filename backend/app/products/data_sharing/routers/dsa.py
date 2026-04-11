from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.dsa_service import DsaService, get_dsa_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/dsa", tags=["dsa"])


class CreateDsaBody(BaseModel):
    title: str
    request_id: UUID | None = None
    counterparty_tenant_id: int | None = None
    conditions: str | None = None


@router.get("/")
async def list_dsas(
    auth_user: AuthUser = Depends(get_current_user),
    service: DsaService = Depends(get_dsa_service),
):
    return await service.list_dsas(auth_user.tenant_id)


@router.post("/")
async def create_dsa(
    body: CreateDsaBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsaService = Depends(get_dsa_service),
):
    return await service.create_dsa(body.model_dump(), auth_user)


@router.get("/{dsa_id}")
async def get_dsa(
    dsa_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsaService = Depends(get_dsa_service),
):
    return await service.get_dsa(dsa_id, auth_user.tenant_id)


@router.post("/{dsa_id}/accept/{side}")
async def accept_dsa(
    dsa_id: UUID, side: str,
    auth_user: AuthUser = Depends(get_current_user),
    service: DsaService = Depends(get_dsa_service),
):
    return await service.accept_dsa(dsa_id, side, auth_user)
