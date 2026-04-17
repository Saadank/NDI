import logging
from uuid import UUID

from app.core.config import get_settings
from app.products.data_sharing.repositories.external_recipient_repository import ExternalRecipientRepository
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.recipient_contact_repository import RecipientContactRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.services.notification_service import NotificationService
from app.products.data_sharing.services.pickup_service import PickupService
from app.products.data_sharing.services.structured_data_service import StructuredDataService
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class ShareFinalizationService:
    """Runs once a share request with sharing_type='external' to an external recipient
    has been fully approved. Materializes structured data if needed, mints a pickup
    token, and queues the invitation email."""

    def __init__(self) -> None:
        self.request_repo = ShareRequestRepository()
        self.file_repo = FileRepository()
        self.recipients = ExternalRecipientRepository()
        self.contacts = RecipientContactRepository()
        self.pickup = PickupService()
        self.structured = StructuredDataService()
        self.notifications = NotificationService()

    async def finalize_if_external(self, request_id: UUID, auth_user: AuthUser) -> None:
        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        if not request:
            return
        if request.get("sharing_type") != "external":
            return
        contact_id = request.get("external_contact_id")
        recipient_id = request.get("external_recipient_id")
        if not contact_id or not recipient_id:
            # External-to-tenant share — this pathway is not our concern.
            return

        # Materialize the structured snapshot (CSV) if needed.
        if request.get("data_type") == "structured":
            existing_files = await self.file_repo.find_by_request(request_id)
            uploaded = [f for f in existing_files if f.get("status") == "uploaded"]
            if not uploaded:
                try:
                    await self.structured.attach_to_request(
                        request_id=request_id,
                        connection_id=request["connection_id"],
                        selection_mode=request["selection_mode"],
                        selected_items=request.get("selected_items"),
                        custom_sql=request.get("custom_sql"),
                        filename=None,
                        auth_user=auth_user,
                    )
                except Exception as exc:
                    logger.exception("Failed to materialize structured snapshot for %s: %s", request_id, exc)
                    raise

        # Mint the pickup token.
        raw_token, token_row = await self.pickup.issue_token_for_request(
            request=request, contact_id=contact_id, actor_id=auth_user.user_id,
        )

        # Look up contact + recipient for the email.
        contact = await self.contacts.find_by_id(contact_id)
        recipient = await self.recipients.find_by_id(recipient_id, request["tenant_id"])
        if not contact or not recipient:
            logger.error("Missing contact/recipient when finalizing %s", request_id)
            return

        settings = get_settings()
        base = settings.FRONTEND_BASE_URL.rstrip("/")
        pickup_url = f"{base}/pickup/{raw_token}"

        await self.notifications.send_pickup_invitation(
            to_email=contact["email"],
            contact_name=contact.get("name") or contact["email"],
            request_title=request["title"],
            requester_org=recipient.get("org_name") or "",
            pickup_url=pickup_url,
            expires_at=token_row["expires_at"],
            max_downloads=token_row["max_downloads"],
            tenant_id=request["tenant_id"],
            request_id=request["id"],
        )


def get_share_finalization_service() -> ShareFinalizationService:
    return ShareFinalizationService()
