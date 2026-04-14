from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.services.group_service import GroupService, get_group_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupBody(BaseModel):
    name: str
    name_ar: str | None = None
    description: str | None = None


class UpdateGroupBody(BaseModel):
    name: str
    name_ar: str | None = None
    description: str | None = None
    is_active: bool = True


class SetDataOwnerBody(BaseModel):
    user_id: int


class MemberBody(BaseModel):
    user_id: int


@router.get("/")
async def list_groups(
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.list_groups(auth_user)


@router.post("/")
async def create_group(
    body: CreateGroupBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.create_group(body.name, body.name_ar, body.description, auth_user)


@router.put("/{group_id}")
async def update_group(
    group_id: int,
    body: UpdateGroupBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.update_group(group_id, body.name, body.name_ar, body.description, body.is_active, auth_user)


@router.delete("/{group_id}")
async def deactivate_group(
    group_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.deactivate_group(group_id, auth_user)


@router.put("/{group_id}/data-owner")
async def set_data_owner(
    group_id: int,
    body: SetDataOwnerBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.set_data_owner(group_id, body.user_id, auth_user)


@router.get("/{group_id}/members")
async def get_group_members(
    group_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.get_group_members(group_id, auth_user)


@router.post("/{group_id}/members")
async def assign_member(
    group_id: int,
    body: MemberBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.assign_member(group_id, body.user_id, auth_user)


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: int,
    user_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: GroupService = Depends(get_group_service),
):
    return await service.remove_member(group_id, user_id, auth_user)
