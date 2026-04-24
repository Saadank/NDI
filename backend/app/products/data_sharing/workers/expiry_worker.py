"""File expiry worker (BRD §3.7).

Responsibilities:
1. Notify receiver + source stewards 48 hours before a file expires.
2. Delete the file's bytes from object storage when the expiry date passes.
   The file row and audit trail are retained forever.
"""
import logging

from app.gateways.cache_gateway import CacheGateway
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_PRE_EXPIRY_WINDOW_HOURS = 48


async def _notify_stakeholders(
    file: dict, request: dict, notification: NotificationService,
    title: str, kind: str,
) -> None:
    # Notify the uploader and — if visible — the receiver/requester sides.
    targets = {
        file.get("uploaded_by"),
        request.get("requester_id"),
    }
    for user_id in targets:
        if not user_id:
            continue
        await notification.create_notification(
            user_id=user_id,
            tenant_id=file["tenant_id"],
            type=kind,
            title=title,
            request_id=file["request_id"],
        )


async def run_expiry_check() -> None:
    files_repo = FileRepository()
    request_repo = ShareRequestRepository()
    object_store = ObjectStoreGateway()
    cache = CacheGateway()
    audit = AuditService()
    notification = NotificationService()

    # --- Pre-expiry notification (T - 48h) ---
    upcoming = await files_repo.find_files_expiring_within(_PRE_EXPIRY_WINDOW_HOURS)
    logger.info("Expiry check: %d files expiring within %dh",
                len(upcoming), _PRE_EXPIRY_WINDOW_HOURS)
    for file in upcoming:
        try:
            request = await request_repo._fetch_row_optional(
                "SELECT * FROM t_share_requests WHERE id = $1", (file["request_id"],)
            ) or {}
            await _notify_stakeholders(
                file, request, notification,
                title=f"Your shared file expires in 48 hours: {file['original_filename']}",
                kind="file_pre_expiry",
            )
            await files_repo.mark_pre_expiry_notified(file["id"])
            await audit.log(
                tenant_id=file["tenant_id"],
                action_type="file.pre_expiry_notified",
                resource_type="file",
                resource_id=str(file["id"]),
                request_id=file["request_id"],
            )
        except Exception as e:
            logger.error("Pre-expiry notice failed for file %s: %s", file["id"], e)

    # --- Delete expired files ---
    expired_files = await files_repo.find_expired_files()
    logger.info("Expiry check: %d expired files to delete", len(expired_files))

    for file in expired_files:
        if cache.sismember("dsplatform:expiry_processed", str(file["id"])):
            continue
        try:
            if object_store.object_exists(file["storage_key"]):
                object_store.delete_object(file["storage_key"])

            await files_repo.soft_delete(file["id"], "expired")
            cache.sadd("dsplatform:expiry_processed", str(file["id"]))

            await audit.log(
                tenant_id=file["tenant_id"],
                action_type="file.expired_deleted",
                resource_type="file",
                resource_id=str(file["id"]),
                request_id=file["request_id"],
            )
            logger.info("Expired and deleted file %s", file["id"])
        except Exception as e:
            logger.error("Failed to process expired file %s: %s", file["id"], e)
