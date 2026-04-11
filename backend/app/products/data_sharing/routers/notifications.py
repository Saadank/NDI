from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.products.data_sharing.services.notification_service import NotificationService, get_notification_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    unread_only: bool = False,
    auth_user: AuthUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.list_notifications(auth_user, unread_only)


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    return await service.mark_read(notification_id, auth_user)
