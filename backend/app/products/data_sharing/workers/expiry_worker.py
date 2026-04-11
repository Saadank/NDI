import logging

from app.gateways.cache_gateway import CacheGateway
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.file_repository import FileRepository

logger = logging.getLogger(__name__)


async def run_expiry_check() -> None:
    repo = FileRepository()
    object_store = ObjectStoreGateway()
    cache = CacheGateway()
    audit = AuditService()

    expired_files = await repo.find_expired_files()
    logger.info(f"Expiry check: found {len(expired_files)} expired files")

    for file in expired_files:
        cache_key = f"dsplatform:expiry_processed:{file['id']}"
        if cache.sismember("dsplatform:expiry_processed", str(file["id"])):
            continue

        try:
            if object_store.object_exists(file["storage_key"]):
                object_store.delete_object(file["storage_key"])

            await repo.soft_delete(file["id"], "expired")
            cache.sadd("dsplatform:expiry_processed", str(file["id"]))

            await audit.log(
                tenant_id=file["tenant_id"],
                action_type="file.expired_deleted",
                resource_type="file",
                resource_id=str(file["id"]),
                request_id=file["request_id"],
            )
            logger.info(f"Expired and deleted file {file['id']}")
        except Exception as e:
            logger.error(f"Failed to process expired file {file['id']}: {e}")
