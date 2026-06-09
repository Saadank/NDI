import logging
import uuid
from datetime import timedelta
from uuid import UUID

from app.core.config import get_settings
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.repositories.tenant_repository import TenantRepository
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.structures.auth_user import AuthUser
from app.products.data_sharing.permissions import can_view_request, require
from app.utils.exceptions import ValidationException
from app.utils.timezone import now

# BRD §3.7 default retention when a tenant has not configured a custom value.
DEFAULT_RETENTION_DAYS = 90

logger = logging.getLogger(__name__)

# Whitelist of allowed MIME types for uploaded attachments. Anything outside
# this set is rejected at upload-initiation time.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset({
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Text / data
    "text/plain",
    "text/csv",
    "application/json",
    "application/xml",
    "text/xml",
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Archives
    "application/zip",
    "application/x-zip-compressed",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
})


class FileService:

    def __init__(self) -> None:
        self.repo = FileRepository()
        self.request_repo = ShareRequestRepository()
        self.tenant_repo = TenantRepository()
        self.object_store = ObjectStoreGateway()
        self.audit = AuditService()

    async def _default_expiry(self, tenant_id: int):
        """Resolve the expiry date for a newly uploaded file when the caller
        did not specify one (BRD §3.7)."""
        tenant = await self.tenant_repo.find_by_id(tenant_id)
        retention = (tenant or {}).get("retention_days") or DEFAULT_RETENTION_DAYS
        return now() + timedelta(days=retention)

    async def initiate_upload(
        self, request_id: UUID, filename: str, size: int,
        mime_type: str | None, sha256_hash: str, auth_user: AuthUser,
        expires_at=None,
    ) -> dict:
        settings = get_settings()
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise ValidationException(f"File size exceeds maximum of {settings.MAX_FILE_SIZE_BYTES} bytes")

        if not mime_type:
            raise ValidationException("mime_type is required")
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationException(f"MIME type '{mime_type}' is not allowed")

        # BRD §1.3 / §2.1: enforce the tenant's contracted storage cap.
        tenant = await self.tenant_repo.find_by_id(auth_user.tenant_id)
        storage_limit_gb = (tenant or {}).get("storage_limit_gb")
        if storage_limit_gb:
            used = await self.repo.total_bytes_for_tenant(auth_user.tenant_id)
            limit_bytes = storage_limit_gb * (1024 ** 3)
            if used + size > limit_bytes:
                raise ValidationException(
                    f"Upload would exceed your organisation's storage limit of "
                    f"{storage_limit_gb} GB"
                )

        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        if request["status"] not in ("draft", "submitted", "in_review", "approved"):
            raise ValidationException("Request is not in a state that allows file uploads")

        storage_key = f"{auth_user.tenant_id}/{request_id}/{uuid.uuid4()}"

        # Apply the BRD §3.7 retention policy if the caller didn't set an
        # explicit expiry. Request-level expiry (if any) wins over the default.
        resolved_expiry = expires_at or request.get("expiry_at")
        if not resolved_expiry:
            resolved_expiry = await self._default_expiry(auth_user.tenant_id)

        file_record = await self.repo.create(
            request_id=request_id,
            tenant_id=auth_user.tenant_id,
            original_filename=filename,
            storage_key=storage_key,
            file_size_bytes=size,
            mime_type=mime_type,
            sha256_hash=sha256_hash,
            uploaded_by=auth_user.user_id,
            expires_at=resolved_expiry,
        )

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="file.upload_initiated",
            resource_type="file", resource_id=str(file_record["id"]),
            actor_id=auth_user.user_id, request_id=request_id,
        )
        return file_record

    async def complete_upload(self, file_id: UUID, data: bytes, received_hash: str, auth_user: AuthUser) -> dict:
        file_record = await self.repo.find_by_id(file_id)
        if file_record["sha256_hash"] != received_hash:
            raise ValidationException("File hash mismatch — integrity check failed")

        self.object_store.put_object(
            key=file_record["storage_key"],
            data=data,
            size=len(data),
            content_type=file_record.get("mime_type") or "application/octet-stream",
        )

        updated = await self.repo.update_status(file_id, "uploaded", uploaded_at=now())

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="file.uploaded",
            resource_type="file", resource_id=str(file_id),
            actor_id=auth_user.user_id, request_id=file_record["request_id"],
        )
        return updated

    async def list_by_request(self, request_id: UUID, auth_user: AuthUser) -> list[dict]:
        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        require(can_view_request(auth_user, request), "You do not have permission to view files for this request")
        return await self.repo.find_by_request(request_id)

    async def get_download_url(self, file_id: UUID, auth_user: AuthUser) -> str:
        file_record = await self.repo.find_by_id(file_id)
        # A file is downloadable once it is in the store and not quarantined:
        # 'uploaded' (no AV scan wired) or 'clean' (scan passed).
        if file_record["status"] not in ("uploaded", "clean"):
            raise ValidationException("File is not available for download")

        # Verify user has access to the parent request
        request = await self.request_repo.find_by_id(file_record["request_id"], auth_user.tenant_id)
        require(can_view_request(auth_user, request), "You do not have permission to download this file")

        url = self.object_store.get_presigned_url(file_record["storage_key"], expires_seconds=60)

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="file.downloaded",
            resource_type="file", resource_id=str(file_id),
            actor_id=auth_user.user_id, request_id=file_record["request_id"],
        )
        return url

    async def delete_file(self, file_id: UUID, reason: str, auth_user: AuthUser) -> None:
        file_record = await self.repo.find_by_id(file_id)

        if self.object_store.object_exists(file_record["storage_key"]):
            self.object_store.delete_object(file_record["storage_key"])

        await self.repo.soft_delete(file_id, reason)

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="file.deleted",
            resource_type="file", resource_id=str(file_id),
            actor_id=auth_user.user_id, request_id=file_record["request_id"],
            metadata={"reason": reason},
        )


def get_file_service() -> FileService:
    return FileService()
