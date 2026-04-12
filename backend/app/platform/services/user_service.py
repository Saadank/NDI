import logging

from app.platform.repositories.user_repository import UserRepository
from app.products.data_sharing.permissions import can_manage_users
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException
from app.utils.pagination import get_pagination_data

logger = logging.getLogger(__name__)


class UserService:

    def __init__(self) -> None:
        self.repo = UserRepository()

    async def list_users(self, tenant_id: int, page: int, limit: int, auth_user: AuthUser) -> dict:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN and auth_user.tenant_id != tenant_id:
            raise ForbiddenException("Access denied")

        users = await self.repo.find_by_tenant(tenant_id, page, limit)
        total = await self.repo.count_by_tenant(tenant_id)
        pagination = get_pagination_data(limit, page, total)
        return {"data": users, **pagination}

    async def get_user(self, user_id: int, auth_user: AuthUser) -> dict:
        user = await self.repo.find_by_id(user_id)
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN and auth_user.tenant_id != user["tenant_id"]:
            raise ForbiddenException("Access denied")
        return user

    async def update_user(self, user_id: int, auth_user: AuthUser, **fields) -> dict:
        user = await self.repo.find_by_id(user_id)
        if not can_manage_users(auth_user):
            raise ForbiddenException("Insufficient permissions")
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role == PlatformRole.ORG_ADMIN and auth_user.tenant_id != user["tenant_id"]:
            raise ForbiddenException("Access denied")
        return await self.repo.update(user_id, **fields)

    async def deactivate_user(self, user_id: int, auth_user: AuthUser) -> str:
        user = await self.repo.find_by_id(user_id)
        if not can_manage_users(auth_user):
            raise ForbiddenException("Insufficient permissions")
        return await self.repo.soft_delete(user_id)


def get_user_service() -> UserService:
    return UserService()
