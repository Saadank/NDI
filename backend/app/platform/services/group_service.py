import re

from app.platform.enums.platform_role import PlatformRole
from app.platform.repositories.group_repository import GroupRepository
from app.platform.repositories.user_repository import UserRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException


ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


def _is_admin(auth_user: AuthUser) -> bool:
    return auth_user.platform_role in ADMIN_ROLES


def _require_admin(auth_user: AuthUser) -> None:
    if not _is_admin(auth_user):
        raise ForbiddenException("Only admins can manage groups")


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100]


class GroupService:

    def __init__(self) -> None:
        self.repo = GroupRepository()
        self.user_repo = UserRepository()

    async def list_groups(self, auth_user: AuthUser) -> list[dict]:
        groups = await self.repo.find_by_tenant(auth_user.tenant_id, include_inactive=_is_admin(auth_user))
        for g in groups:
            g["member_count"] = await self.repo.count_members(g["id"])
            # Resolve data owner name
            if g.get("data_owner_id"):
                owner = await self.user_repo.find_by_id(g["data_owner_id"])
                g["data_owner_name"] = f"{owner.get('first_name', '')} {owner.get('last_name', '')}".strip() if owner else None
            else:
                g["data_owner_name"] = None
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

    async def set_data_owner(self, group_id: int, user_id: int, auth_user: AuthUser) -> dict:
        _require_admin(auth_user)
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        return await self.repo.update(group_id, data_owner_id=user_id)

    def _can_manage_group_members(self, auth_user: AuthUser, group: dict) -> bool:
        """Admin or the data owner of this specific group can manage members."""
        if _is_admin(auth_user):
            return True
        return group.get("data_owner_id") == auth_user.user_id

    async def get_group_members(self, group_id: int, auth_user: AuthUser) -> list[dict]:
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        if not self._can_manage_group_members(auth_user, group):
            raise ForbiddenException("You do not have permission to view this group's members")
        return await self.repo.find_members(group_id)

    async def assign_member(self, group_id: int, user_id: int, auth_user: AuthUser) -> dict:
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        if not self._can_manage_group_members(auth_user, group):
            raise ForbiddenException("You do not have permission to manage this group's members")
        return await self.user_repo.update(user_id, group_id=group_id)

    async def remove_member(self, group_id: int, user_id: int, auth_user: AuthUser) -> dict:
        group = await self.repo.find_by_id(group_id)
        if not group or group["tenant_id"] != auth_user.tenant_id:
            raise ValidationException("Group not found")
        if not self._can_manage_group_members(auth_user, group):
            raise ForbiddenException("You do not have permission to manage this group's members")
        return await self.user_repo.update(user_id, group_id=None)


def get_group_service() -> GroupService:
    return GroupService()
