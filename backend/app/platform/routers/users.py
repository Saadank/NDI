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


class DeactivateUserBody(BaseModel):
    """Optional payload for POST /users/{id}/deactivate.

    When `transfer_to_user_id` is provided, the deactivated user's open
    responsibilities are routed to the named delegate via the existing
    delegation pipeline (BRD §2.3) before the account is disabled. Pass
    `null` (or omit) to deactivate without transfer — only safe when the
    user has no in-flight responsibilities.
    """
    transfer_to_user_id: int | None = None


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


@router.post("/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    body: DeactivateUserBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Deactivate a user account (Org Admin / Platform Admin only).

    The Pencil-designed flow lets the admin name a delegate to receive any
    open responsibilities. We implement that by piping through the existing
    delegation pipeline: set the deactivated user's delegation pointer so
    any in-flight approvals re-route immediately, then flip is_active=False.
    The account row stays in t_users with a soft trail — a hard delete is
    not exposed in the UI.
    """
    if auth_user.platform_role not in ADMIN_ROLES:
        raise ForbiddenException("Only admins can deactivate users")
    repo = UserRepository()
    target = await repo.find_by_id(user_id)
    if not target:
        raise ForbiddenException("User not found")
    # Org admins can only act inside their own tenant.
    if (
        auth_user.platform_role == PlatformRole.ORG_ADMIN
        and target.get("tenant_id") != auth_user.tenant_id
    ):
        raise ForbiddenException("Cannot deactivate users from another tenant")

    # 1) Reassign open responsibilities via delegation when requested.
    #    set_delegation is a direct repo update on t_users — no need to
    #    construct a fake AuthUser context for the delegation service.
    if body.transfer_to_user_id is not None:
        await repo.set_delegation(
            user_id=user_id,
            delegate_to=body.transfer_to_user_id,
            reason="Account deactivation transfer",
        )

    # 2) Disable the account.
    return await repo.update(user_id, is_active=False)
