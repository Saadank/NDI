import re

from app.platform.enums.platform_role import PlatformRole
from app.platform.repositories.group_repository import GroupRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException


ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


def _require_admin(auth_user: AuthUser) -> None:
    if auth_user.platform_role not in ADMIN_ROLES:
        raise ForbiddenException("Only admins can manage groups")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100]


class GroupService:

    def __init__(self) -> None:
        self.repo = GroupRepository()

    async def list_groups(self, auth_user: AuthUser) -> list[dict]:
        groups = await self.repo.find_by_tenant(auth_user.tenant_id, include_inactive=auth_user.platform_role in ADMIN_ROLES)
        for g in groups:
            g["member_count"] = await self.repo.count_members(g["id"])
        return groups

    async def create_group(self, name: str, name_ar: str | None, description: str | None,
                           auth_user: AuthUser) -> dict:
        _require_admin(auth_user)
        slug = _slugify(name)
        existing = await self.repo.find_by_slug(auth_user.tenant_id, slug)
        if existing:
            raise ValidationException(f"A group with slug '{slug}' already exists")
        return await self.repo.create(auth_user.tenant_id, name, name_ar, slug, description)

    async def update_group(self, group_id: int, name: str, name_ar: str | None,
                           description: str | None, is_active: bool, auth_user: AuthUser) -> dict:
        _require_admin(auth_user)
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        return await self.repo.update(group_id, name=name, name_ar=name_ar, description=description, is_active=is_active)

    async def deactivate_group(self, group_id: int, auth_user: AuthUser) -> dict:
        _require_admin(auth_user)
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        return await self.repo.update(group_id, is_active=False)

    async def get_group_members(self, group_id: int, auth_user: AuthUser) -> list[dict]:
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        return await self.repo.find_members(group_id)


def get_group_service() -> GroupService:
    return GroupService()
