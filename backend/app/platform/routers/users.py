from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.platform.services.user_service import UserService, get_user_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/users", tags=["users"])


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
