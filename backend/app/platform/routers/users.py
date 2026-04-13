from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.platform.repositories.user_repository import UserRepository
from app.platform.services.user_service import UserService, get_user_service
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/users", tags=["users"])

ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


class AssignGroupBody(BaseModel):
    group_id: int | None


@router.get("/")
async def list_users(
    page: int = 1, limit: int = 20,
    auth_user: AuthUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return await service.list_users(auth_user.tenant_id, page, limit, auth_user)


@router.get("/me")
async def get_current(auth_user: AuthUser = Depends(get_current_user)):
    return auth_user.model_dump()


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return await service.get_user(user_id, auth_user)


@router.put("/{user_id}/group")
async def assign_user_group(
    user_id: int,
    body: AssignGroupBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    if auth_user.platform_role not in ADMIN_ROLES:
        raise ForbiddenException("Only admins can assign groups")
    repo = UserRepository()
    return await repo.update(user_id, group_id=body.group_id)
