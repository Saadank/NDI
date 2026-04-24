from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.platform.services.tenant_service import TenantService, get_tenant_service
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException

router = APIRouter(prefix="/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    tenant_type: str = "internal_org"
    name_ar: str | None = None
    dpo_name: str | None = None
    dpo_email: str | None = None


class RetentionPolicyRequest(BaseModel):
    # BRD §3.7 allows 30 / 60 / 90 / 180 days only.
    retention_days: int = Field(..., description="30, 60, 90, or 180")


class QuotaRequest(BaseModel):
    storage_limit_gb: int | None = None
    seat_limit: int | None = None


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


@router.put("/{tenant_id}/retention-policy")
async def set_retention_policy(
    tenant_id: int,
    body: RetentionPolicyRequest,
    auth_user: AuthUser = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    """Org Admin sets the org-wide default retention for uploaded files."""
    if auth_user.platform_role not in (PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN):
        raise ForbiddenException("Only admins can change the retention policy")
    if body.retention_days not in (30, 60, 90, 180):
        raise ValidationException("retention_days must be one of 30, 60, 90, 180")
    return await service.update_tenant(tenant_id, auth_user, retention_days=body.retention_days)


@router.put("/{tenant_id}/quotas")
async def set_quotas(
    tenant_id: int,
    body: QuotaRequest,
    auth_user: AuthUser = Depends(get_current_user),
    service: TenantService = Depends(get_tenant_service),
):
    """Platform Admin sets storage and seat caps per the contract (BRD §1.3)."""
    if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN:
        raise ForbiddenException("Only platform admins can change tenant quotas")
    update = {}
    if body.storage_limit_gb is not None:
        if body.storage_limit_gb < 0:
            raise ValidationException("storage_limit_gb must be non-negative")
        update["storage_limit_gb"] = body.storage_limit_gb
    if body.seat_limit is not None:
        if body.seat_limit < 0:
            raise ValidationException("seat_limit must be non-negative")
        update["seat_limit"] = body.seat_limit
    if not update:
        raise ValidationException("Provide at least one of storage_limit_gb or seat_limit")
    return await service.update_tenant(tenant_id, auth_user, **update)
