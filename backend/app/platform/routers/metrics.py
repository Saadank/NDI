"""Platform-Admin-only metadata view (BRD §2.1 CRITICAL rule).

The vendor can see organisation health — user counts, request counts, storage
usage — but never the request content, file bytes, audit details, or any
other data-controller content.
"""
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.platform.repositories.tenant_repository import TenantRepository
from app.platform.repositories.user_repository import UserRepository
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/metrics", tags=["metrics"])


class _MetricsRepo(PostgresqlAsyncRepository):

    async def request_counts(self, tenant_id: int) -> dict:
        rows = await self._fetch_all(
            "SELECT status, COUNT(*) AS n FROM t_share_requests "
            "WHERE tenant_id = $1 AND deleted_at IS NULL GROUP BY status",
            (tenant_id,),
        )
        return {r["status"]: r["n"] for r in rows}

    async def active_products(self, tenant_id: int) -> list[str]:
        rows = await self._fetch_all(
            "SELECT p.slug FROM t_tenant_products tp "
            "JOIN t_products p ON p.id = tp.product_id "
            "WHERE tp.tenant_id = $1 AND tp.enabled = TRUE",
            (tenant_id,),
        )
        return [r["slug"] for r in rows]


def _require_platform_admin(auth_user: AuthUser) -> None:
    if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN:
        raise ForbiddenException("Only platform admins can view tenant metrics")


@router.get("/tenants/{tenant_id}")
async def tenant_metrics(
    tenant_id: int,
    auth_user: AuthUser = Depends(get_current_user),
):
    _require_platform_admin(auth_user)

    tenants = TenantRepository()
    users = UserRepository()
    files = FileRepository()
    metrics_repo = _MetricsRepo()

    tenant = await tenants.find_by_id(tenant_id)
    user_count = await users.count_active(tenant_id)
    storage_bytes = await files.total_bytes_for_tenant(tenant_id)
    requests = await metrics_repo.request_counts(tenant_id)
    products = await metrics_repo.active_products(tenant_id)

    storage_limit_gb = tenant.get("storage_limit_gb")
    seat_limit = tenant.get("seat_limit")
    storage_gb_used = storage_bytes / (1024 ** 3)

    return {
        "tenant": {
            "id": tenant["id"],
            "name": tenant["name"],
            "slug": tenant["slug"],
            "is_active": tenant["is_active"],
        },
        "active_products": products,
        "users": {
            "active": user_count,
            "seat_limit": seat_limit,
            "seats_remaining": (
                max(seat_limit - user_count, 0) if seat_limit is not None else None
            ),
        },
        "storage": {
            "bytes_used": storage_bytes,
            "gb_used": round(storage_gb_used, 3),
            "gb_limit": storage_limit_gb,
            "percent_used": (
                round(storage_gb_used / storage_limit_gb * 100, 1)
                if storage_limit_gb else None
            ),
        },
        "requests": requests,
        "retention_days": tenant.get("retention_days"),
    }
