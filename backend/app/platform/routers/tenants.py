from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.services.tenant_service import TenantService, get_tenant_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    tenant_type: str = "internal_org"
    name_ar: str | None = None
    dpo_name: str | None = None
    dpo_email: str | None = None


@router.get("/")
async def list_tenants(auth_user: AuthUser = Depends(get_current_user), service: TenantService = Depends(get_tenant_service)):
    return await service.list_tenants(auth_user)


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: int, auth_user: AuthUser = Depends(get_current_user), service: TenantService = Depends(get_tenant_service)):
    return await service.get_tenant(tenant_id, auth_user)


@router.post("/")
async def create_tenant(body: CreateTenantRequest, auth_user: AuthUser = Depends(get_current_user), service: TenantService = Depends(get_tenant_service)):
    return await service.create_tenant(
        name=body.name, slug=body.slug, tenant_type=body.tenant_type,
        name_ar=body.name_ar, dpo_name=body.dpo_name, dpo_email=body.dpo_email,
        auth_user=auth_user,
    )
