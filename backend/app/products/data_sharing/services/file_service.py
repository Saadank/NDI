import logging
import uuid
from uuid import UUID

from app.core.config import get_settings
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ValidationException
from app.utils.timezone import now

logger = logging.getLogger(__name__)


class FileService:

    def __init__(self) -> None:
        self.repo = FileRepository()
        self.request_repo = ShareRequestRepository()
        self.object_store = ObjectStoreGateway()
        self.audit = AuditService()

    async def initiate_upload(
        self, request_id: UUID, filename: str, size: int,
        mime_type: str | None, sha256_hash: str, auth_user: AuthUser,
        expires_at=None,
    ) -> dict:
        settings = get_settings()
        if size > settings.MAX_FILE_SIZE_BYTES:
            raise ValidationException(f"File size exceeds maximum of {settings.MAX_FILE_SIZE_BYTES} bytes")

        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        if request["status"] not in ("submitted", "in_review", "approved"):
            raise ValidationException("Request is not in a state that allows file uploads")

        storage_key = f"{auth_user.tenant_id}/{request_id}/{uuid.uuid4()}"

        file_record = await self.repo.create(
            request_id=request_id,
            tenant_id=auth_user.tenant_id,
            original_filename=filename,
            storage_key=storage_key,
            file_size_bytes=size,
            mime_type=mime_type,
            sha256_hash=sha256_hash,
            uploaded_by=auth_user.user_id,
            expires_at=expires_at,
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

    async def get_download_url(self, file_id: UUID, auth_user: AuthUser) -> str:
        file_record = await self.repo.find_by_id(file_id)
        if file_record["status"] != "uploaded":
            raise ValidationException("File is not available for download")

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
