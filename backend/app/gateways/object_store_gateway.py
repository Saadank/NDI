import logging
from io import BytesIO

from minio import Minio

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ObjectStoreGateway:

    def __init__(self) -> None:
        settings = get_settings()
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.default_bucket = settings.MINIO_BUCKET
        self._ensure_bucket(self.default_bucket)

        # Separate client for presigned URLs so the signature matches localhost.
        # Region is set explicitly to avoid a network call from inside Docker.
        self._presign_client = Minio(
            endpoint="localhost:9000",
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,
            region="us-east-1",
        )

    def _ensure_bucket(self, bucket: str) -> None:
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info(f"Created bucket: {bucket}")

    def put_object(
        self,
        key: str,
        data: bytes | BytesIO,
        size: int,
        content_type: str = "application/octet-stream",
        bucket: str | None = None,
    ) -> None:
        bucket = bucket or self.default_bucket
        if isinstance(data, bytes):
            data = BytesIO(data)
        self.client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=data,
            length=size,
            content_type=content_type,
        )
        logger.info(f"Stored object: {bucket}/{key} ({size} bytes)")

    def get_presigned_url(self, key: str, expires_seconds: int = 60, bucket: str | None = None) -> str:
        from datetime import timedelta

        bucket = bucket or self.default_bucket
        url = self._presign_client.presigned_get_object(
            bucket_name=bucket,
            object_name=key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    def delete_object(self, key: str, bucket: str | None = None) -> None:
        bucket = bucket or self.default_bucket
        self.client.remove_object(bucket_name=bucket, object_name=key)
        logger.info(f"Deleted object: {bucket}/{key}")

    def object_exists(self, key: str, bucket: str | None = None) -> bool:
        bucket = bucket or self.default_bucket
        try:
            self.client.stat_object(bucket_name=bucket, object_name=key)
            return True
        except Exception:
            return False
