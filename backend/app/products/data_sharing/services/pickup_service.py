import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.config import get_settings
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.permissions import can_manage_recipients, require
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.pickup_token_repository import PickupTokenRepository
from app.products.data_sharing.repositories.recipient_contact_repository import RecipientContactRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import (
    ExpiredException, ForbiddenException, ResourceNotFoundException, ValidationException,
)

logger = logging.getLogger(__name__)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


class PickupService:

    def __init__(self) -> None:
        self.tokens = PickupTokenRepository()
        self.contacts = RecipientContactRepository()
        self.files = FileRepository()
        self.request_repo = ShareRequestRepository()
        self.object_store = ObjectStoreGateway()
        self.audit = AuditService()

    # ------------------------------------------------------------------
    # Minting
    # ------------------------------------------------------------------

    async def issue_token_for_request(
        self, request: dict, contact_id: int, actor_id: int | None,
    ) -> tuple[str, dict]:
        settings = get_settings()
        raw = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.PICKUP_TOKEN_TTL_HOURS)
        row = await self.tokens.create(
            tenant_id=request["tenant_id"],
            share_request_id=request["id"],
            contact_id=contact_id,
            token_hash=token_hash,
            expires_at=expires_at,
            max_downloads=settings.PICKUP_TOKEN_MAX_DOWNLOADS,
            created_by=actor_id,
        )
        await self.audit.log(
            tenant_id=request["tenant_id"], action_type="pickup.token_issued",
            resource_type="pickup_token", resource_id=str(row["id"]),
            actor_id=actor_id, request_id=request["id"],
            metadata={
                "contact_id": contact_id,
                "external_recipient_id": request.get("external_recipient_id"),
                "expires_at": expires_at.isoformat(),
                "max_downloads": row["max_downloads"],
            },
        )
        return raw, row

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    async def verify_token(self, raw_token: str) -> dict:
        if not raw_token or len(raw_token) < 20:
            raise ResourceNotFoundException("Pickup link not found")
        token_hash = _hash_token(raw_token)
        token = await self.tokens.find_by_token_hash(token_hash)
        if not token:
            raise ResourceNotFoundException("Pickup link not found")
        if token["revoked_at"] is not None:
            raise ForbiddenException("This pickup link has been revoked")
        now = datetime.now(timezone.utc)
        expires_at = token["expires_at"]
        # asyncpg returns timezone-aware datetimes for TIMESTAMPTZ; this compares safely.
        if expires_at <= now:
            # Emit once; it's fine if we emit multiple times on repeated hits.
            await self.audit.log(
                tenant_id=token["tenant_id"], action_type="pickup.token_expired",
                resource_type="pickup_token", resource_id=str(token["id"]),
                request_id=token["share_request_id"],
                metadata={"contact_id": token["contact_id"]},
            )
            raise ExpiredException("This pickup link has expired")
        if token["download_count"] >= token["max_downloads"]:
            raise ForbiddenException("This pickup link has reached its download limit")
        return token

    async def mark_opened_if_needed(self, token: dict, ip: str | None, ua: str | None) -> dict:
        if token["first_opened_at"] is not None:
            return token
        updated = await self.tokens.mark_opened(token["id"])
        await self.audit.log(
            tenant_id=token["tenant_id"], action_type="pickup.opened",
            resource_type="pickup_token", resource_id=str(token["id"]),
            actor_ip=ip, request_id=token["share_request_id"],
            metadata={"contact_id": token["contact_id"], "user_agent": (ua or "")[:512]},
        )
        return updated

    # ------------------------------------------------------------------
    # DPA acceptance
    # ------------------------------------------------------------------

    async def accept_dpa(self, token: dict, ip: str | None, ua: str | None) -> dict:
        if token["dpa_accepted_at"] is not None:
            return token
        updated = await self.tokens.record_dpa(token["id"], ip, (ua or "")[:512])
        # Verify the contact's email the first time they accept.
        await self.contacts.mark_verified(token["contact_id"])
        await self.audit.log(
            tenant_id=token["tenant_id"], action_type="pickup.dpa_accepted",
            resource_type="pickup_token", resource_id=str(token["id"]),
            actor_ip=ip, request_id=token["share_request_id"],
            metadata={"contact_id": token["contact_id"], "user_agent": (ua or "")[:512]},
        )
        return updated

    # ------------------------------------------------------------------
    # Artifact listing / downloading
    # ------------------------------------------------------------------

    async def list_artifacts(self, token: dict) -> list[dict]:
        rows = await self.files.find_by_request(token["share_request_id"])
        safe = []
        for r in rows:
            if r.get("status") != "uploaded":
                continue
            safe.append({
                "id": str(r["id"]),
                "filename": r["original_filename"],
                "size_bytes": r["file_size_bytes"],
                "mime_type": r.get("mime_type"),
                "sha256_hash": r.get("sha256_hash"),
                "uploaded_at": r.get("uploaded_at"),
            })
        return safe

    async def generate_download_url(self, token: dict, file_id: UUID, ip: str | None) -> str:
        file_record = await self.files.find_by_id(file_id)
        if file_record["request_id"] != token["share_request_id"]:
            raise ForbiddenException("This file does not belong to the pickup link")
        if file_record.get("status") != "uploaded":
            raise ValidationException("File is not available for download")

        # Atomic gate: only bumps if not revoked/expired/exhausted.
        bumped = await self.tokens.increment_download(token["id"])
        if not bumped:
            raise ForbiddenException("Pickup link is no longer valid for downloads")

        settings = get_settings()
        url = self.object_store.get_presigned_url(
            file_record["storage_key"],
            expires_seconds=settings.PICKUP_DOWNLOAD_URL_TTL_SECONDS,
        )
        await self.audit.log(
            tenant_id=token["tenant_id"], action_type="pickup.file_downloaded",
            resource_type="pickup_token", resource_id=str(token["id"]),
            actor_ip=ip, request_id=token["share_request_id"],
            metadata={
                "contact_id": token["contact_id"],
                "file_id": str(file_id),
                "download_count_after": bumped["download_count"],
            },
        )
        return url

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    async def revoke(self, token_id: UUID, auth_user: AuthUser, reason: str | None) -> dict:
        require(can_manage_recipients(auth_user), "You cannot revoke pickup tokens")
        token = await self.tokens.find_by_id(token_id)
        if not token:
            raise ResourceNotFoundException("Pickup token not found")
        if token["tenant_id"] != auth_user.tenant_id:
            raise ResourceNotFoundException("Pickup token not found")
        if token["revoked_at"] is not None:
            return token
        updated = await self.tokens.revoke(token_id, auth_user.user_id, reason)
        await self.audit.log(
            tenant_id=token["tenant_id"], action_type="pickup.token_revoked",
            resource_type="pickup_token", resource_id=str(token_id),
            actor_id=auth_user.user_id, request_id=token["share_request_id"],
            metadata={"reason": reason},
        )
        # Strip hash in response.
        updated.pop("token_hash", None)
        return updated


def get_pickup_service() -> PickupService:
    return PickupService()
