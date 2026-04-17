import html
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

    async def send_pickup_invitation(
        self, to_email: str, contact_name: str, request_title: str,
        requester_org: str, pickup_url: str, expires_at,
        max_downloads: int, tenant_id: int, request_id: UUID,
    ) -> dict:
        """Queue a magic-link pickup invitation email to an external recipient contact."""
        safe_name = html.escape(contact_name or to_email)
        safe_title = html.escape(request_title or "")
        safe_org = html.escape(requester_org or "")
        safe_url = html.escape(pickup_url, quote=True)
        safe_expiry = html.escape(expires_at.isoformat() if hasattr(expires_at, "isoformat") else str(expires_at))
        body = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,Helvetica,sans-serif;color:#1f2937;background:#f3f4f6;padding:24px;margin:0;">
  <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:8px;padding:32px;border:1px solid #e5e7eb;">
    <h2 style="margin:0 0 16px 0;color:#0f172a;">Secure file pickup: {safe_title}</h2>
    <p style="margin:0 0 12px 0;">Hello {safe_name},</p>
    <p style="margin:0 0 12px 0;">
      <strong>{safe_org}</strong> has shared data with you through a secure pickup portal.
    </p>
    <p style="margin:0 0 20px 0;">
      Click the link below to review the data-sharing agreement and download the files.
      This link is personal to you — please do not forward this email.
    </p>
    <p style="margin:0 0 24px 0;">
      <a href="{safe_url}"
         style="display:inline-block;background:#2563eb;color:#ffffff;padding:12px 24px;
                border-radius:6px;text-decoration:none;font-weight:600;">
        Open pickup portal
      </a>
    </p>
    <p style="margin:0 0 8px 0;color:#6b7280;font-size:13px;">
      Link expires: <strong>{safe_expiry}</strong>
    </p>
    <p style="margin:0 0 24px 0;color:#6b7280;font-size:13px;">
      Maximum downloads: <strong>{max_downloads}</strong>
    </p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
    <p style="margin:0;color:#9ca3af;font-size:12px;">
      This is a secure, audited channel. All actions on the pickup portal are logged
      under the sharing organisation's data-protection records.
    </p>
  </div>
</body></html>"""
        return await self.repo.queue_email(
            to_email=to_email,
            subject=f"Secure file pickup: {request_title}",
            html_body=body,
            request_id=request_id,
        )


def get_notification_service() -> NotificationService:
    return NotificationService()
