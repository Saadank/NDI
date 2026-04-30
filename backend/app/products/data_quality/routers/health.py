from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/health", tags=["dq-health"])


@router.get("/")
async def dq_health(auth_user: AuthUser = Depends(get_current_user)):
    return {
        "status": "ok",
        "product": "data_quality",
        "tenant_id": auth_user.tenant_id,
        "user_id": auth_user.user_id,
    }
