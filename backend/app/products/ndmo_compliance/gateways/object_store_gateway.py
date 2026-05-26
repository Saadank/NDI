"""NDMO-side wrapper over the platform ObjectStoreGateway.

The shared `app.gateways.object_store_gateway.ObjectStoreGateway` is
single-bucket-by-key-prefix.  NDMO follows the cortex pattern of three
state buckets (unscanned / clean / infected) so that MinIO's
bucket-notify can target only the unscanned bucket as the workflow
trigger.  Tenant prefix lives inside the key, not the bucket name.

Bucket conventions:

  * ``ndmo-unscanned``  — landing zone for presigned PUTs
  * ``ndmo-clean``      — passed ClamAV; ready for extraction
  * ``ndmo-infected``   — quarantine; analyst-visible audit trail

Key format ``{tenant_id}/{document_id}/{uuid4()}.{ext}``.
"""

from __future__ import annotations

import logging
from typing import Final

from app.gateways.object_store_gateway import ObjectStoreGateway as PlatformObjectStoreGateway

logger = logging.getLogger(__name__)


BUCKET_UNSCANNED: Final[str] = "ndmo-unscanned"
BUCKET_CLEAN: Final[str] = "ndmo-clean"
BUCKET_INFECTED: Final[str] = "ndmo-infected"


class NdmoObjectStoreGateway:
    """Thin wrapper that adds the helpers the NDMO workflow needs.

    Reuses the platform ObjectStoreGateway's MinIO client + presigned
    machinery (so we inherit credentials, dev-localhost rewriting, etc.).
    """

    def __init__(self) -> None:
        self._platform = PlatformObjectStoreGateway()
        for bucket in (BUCKET_UNSCANNED, BUCKET_CLEAN, BUCKET_INFECTED):
            self._platform._ensure_bucket(bucket)  # noqa: SLF001 — intentional re-use

    # ---- reads -----------------------------------------------------------

    def get_object_bytes(self, *, bucket: str, key: str) -> bytes:
        """Download an object into memory."""
        resp = self._platform.client.get_object(bucket_name=bucket, object_name=key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    # ---- writes ----------------------------------------------------------

    def copy_object(
        self,
        *,
        source_bucket: str,
        source_key: str,
        destination_bucket: str,
        destination_key: str,
    ) -> None:
        from minio.commonconfig import CopySource
        self._platform.client.copy_object(
            bucket_name=destination_bucket,
            object_name=destination_key,
            source=CopySource(source_bucket, source_key),
        )
        logger.info(
            "Copied %s/%s -> %s/%s",
            source_bucket, source_key, destination_bucket, destination_key,
        )

    def remove_object(self, *, bucket: str, key: str) -> None:
        self._platform.client.remove_object(bucket_name=bucket, object_name=key)
        logger.info("Removed %s/%s", bucket, key)

    # ---- presigned ops --------------------------------------------------

    def presigned_put(self, *, bucket: str, key: str, expires_seconds: int = 600) -> str:
        from datetime import timedelta
        return self._platform._presign_client.presigned_put_object(  # noqa: SLF001
            bucket_name=bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )

    def presigned_get(self, *, bucket: str, key: str, expires_seconds: int = 60) -> str:
        from datetime import timedelta
        return self._platform._presign_client.presigned_get_object(  # noqa: SLF001
            bucket_name=bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
