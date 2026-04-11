import logging

from app.platform.repositories.tenant_repository import TenantRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

logger = logging.getLogger(__name__)


class TenantService:

    def __init__(self) -> None:
        self.repo = TenantRepository()

    async def list_tenants(self, auth_user: AuthUser) -> list[dict]:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN:
            raise ForbiddenException("Only platform admins can list all tenants")
        return await self.repo.find_all()

    async def get_tenant(self, tenant_id: int, auth_user: AuthUser) -> dict:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN and auth_user.tenant_id != tenant_id:
            raise ForbiddenException("Access denied")
        return await self.repo.find_by_id(tenant_id)

    async def create_tenant(self, name: str, slug: str, tenant_type: str, name_ar: str | None, dpo_name: str | None, dpo_email: str | None, auth_user: AuthUser) -> dict:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN:
            raise ForbiddenException("Only platform admins can create tenants")
        return await self.repo.create(name, slug, tenant_type, name_ar, dpo_name, dpo_email)

    async def update_tenant(self, tenant_id: int, auth_user: AuthUser, **fields) -> dict:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN and auth_user.tenant_id != tenant_id:
            raise ForbiddenException("Access denied")
        return await self.repo.update(tenant_id, **fields)


def get_tenant_service() -> TenantService:
    return TenantService()
