import logging
from uuid import UUID

from app.products.data_sharing.repositories.notification_repository import NotificationRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class NotificationService:

    def __init__(self) -> None:
        self.repo = NotificationRepository()

    async def create_notification(
        self, user_id: int, tenant_id: int, type: str, title: str,
        body: str | None = None, request_id: UUID | None = None,
    ) -> dict:
        return await self.repo.create(user_id, tenant_id, type, title, body, request_id)

    async def list_notifications(self, auth_user: AuthUser, unread_only: bool = False) -> list[dict]:
        return await self.repo.find_by_user(auth_user.user_id, unread_only)

    async def mark_read(self, notification_id: UUID, auth_user: AuthUser) -> dict:
        return await self.repo.mark_read(notification_id, auth_user.user_id)

    async def queue_email(self, to_email: str, subject: str, html_body: str, request_id: UUID | None = None) -> dict:
        return await self.repo.queue_email(to_email, subject, html_body, request_id)


def get_notification_service() -> NotificationService:
    return NotificationService()
