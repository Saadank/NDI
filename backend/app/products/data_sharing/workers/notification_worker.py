import logging

from app.gateways.email_gateway import EmailGateway
from app.core.config import get_settings
from app.products.data_sharing.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


async def run_notification_worker() -> None:
    repo = NotificationRepository()
    email_gateway = EmailGateway()
    settings = get_settings()

    pending = await repo.find_pending_emails()
    logger.info(f"Notification worker: processing {len(pending)} emails")

    for email_record in pending:
        try:
            await email_gateway.send_html_email(
                from_email=settings.EMAIL_FROM,
                to_email=email_record["to_email"],
                subject=email_record["subject"],
                body=email_record["html_body"],
            )
            await repo.update_email_status(email_record["id"], "sent")
            logger.info(f"Sent email {email_record['id']} to {email_record['to_email']}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to send email {email_record['id']}: {error_msg}")
            status = "failed" if email_record["attempts"] >= 2 else "pending"
            await repo.update_email_status(email_record["id"], status, error_msg)
