from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.platform.repositories.user_repository import UserRepository
from app.platform.services.delegation_service import DelegationService, get_delegation_service
from app.platform.services.user_service import UserService, get_user_service
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/users", tags=["users"])

ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


class AssignGroupBody(BaseModel):
    group_id: int | None


class DelegationBody(BaseModel):
    """Payload for POST /users/me/delegation.

    Set `delegate_to_user_id = null` to clear an existing delegation.
    """
    delegate_to_user_id: int | None = None
    delegation_start: datetime | None = None
    delegation_end: datetime | None = None
    reason: str | None = None


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


@router.post("/me/delegation")
async def set_my_delegation(
    body: DelegationBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: DelegationService = Depends(get_delegation_service),
):
    """Set or clear the caller's out-of-office delegation (BRD §2.3)."""
    updated = await service.set_delegation(
        auth_user=auth_user,
        delegate_to_user_id=body.delegate_to_user_id,
        start=body.delegation_start,
        end=body.delegation_end,
        reason=body.reason,
    )
    # Strip sensitive columns before returning.
    safe = {k: v for k, v in updated.items() if k not in ("keycloak_id",)}
    return safe


@router.delete("/me/delegation")
async def clear_my_delegation(
    auth_user: AuthUser = Depends(get_current_user),
    service: DelegationService = Depends(get_delegation_service),
):
    updated = await service.set_delegation(
        auth_user=auth_user, delegate_to_user_id=None,
        start=None, end=None, reason=None,
    )
    return {"delegation_to_user_id": updated.get("delegation_to_user_id")}


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
