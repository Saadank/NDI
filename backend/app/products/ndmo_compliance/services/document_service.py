"""Document service — HTTP-side orchestration.

  * ``initiate_upload``: create a t_ndmo_documents row, return a presigned
    PUT URL into the ``ndmo-unscanned`` bucket.  The MinIO bucket-notify
    webhook will kick off the Restate workflow once the upload lands.
  * ``list_documents`` / ``get_document``: standard read paths.
  * ``get_workflow_status``: forward to Restate's GetStatus handler so the
    frontend can show a tree-shaped progress widget per the cortex pattern.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.products.ndmo_compliance.entities.document import Document
from app.products.ndmo_compliance.gateways.object_store_gateway import (
    BUCKET_UNSCANNED,
    NdmoObjectStoreGateway,
)
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InitiateUploadResult:
    document_id: str
    minio_key: str
    presigned_put_url: str
    expires_seconds: int


class DocumentService:
    """Stateless service composing the repository, storage, and Restate."""

    def __init__(self) -> None:
        self._documents = DocumentRepository()
        self._storage = NdmoObjectStoreGateway()
        self._restate_admin_url = (
            os.environ.get("RESTATE_INGRESS_URL") or "http://restate:8080"
        )

    # ---- HTTP-facing methods --------------------------------------------

    async def initiate_upload(
        self,
        *,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        cycle_id: int | None,
        auth_user: AuthUser,
    ) -> InitiateUploadResult:
        document_uuid = uuid.uuid4()
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        minio_key = f"{auth_user.tenant_id}/{document_uuid}/{uuid.uuid4()}.{extension}"

        await self._documents.create(
            tenant_id=auth_user.tenant_id,
            file_name=file_name,
            minio_key=minio_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            uploaded_by=auth_user.user_id,
            cycle_id=cycle_id,
        )

        url = self._storage.presigned_put(
            bucket=BUCKET_UNSCANNED, key=minio_key, expires_seconds=600
        )
        return InitiateUploadResult(
            document_id=str(document_uuid),
            minio_key=minio_key,
            presigned_put_url=url,
            expires_seconds=600,
        )

    async def list_documents(
        self, *, auth_user: AuthUser, cycle_id: int | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[Document]:
        return await self._documents.list_by_tenant(
            tenant_id=auth_user.tenant_id, cycle_id=cycle_id,
            limit=limit, offset=offset,
        )

    async def get_document(self, *, document_id: uuid.UUID, auth_user: AuthUser) -> Document:
        return await self._documents.find_by_id(
            document_id=document_id, tenant_id=auth_user.tenant_id
        )

    async def get_workflow_status(
        self, *, document_id: uuid.UUID, auth_user: AuthUser,
    ) -> dict[str, Any] | None:
        """Call Restate's GetStatus handler to retrieve the live status tree."""
        await self._documents.find_by_id(           # 404 if not theirs
            document_id=document_id, tenant_id=auth_user.tenant_id
        )
        url = (
            f"{self._restate_admin_url}/NdmoDocumentIngestionWorkflow/"
            f"{document_id}/GetStatus"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={})
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    async def trigger_workflow(
        self, *, document_id: uuid.UUID, minio_key: str, tenant_id: int,
    ) -> None:
        """Fire the Restate workflow.  Called by the MinIO webhook handler.

        Uses Restate's HTTP ingress (workflow.send semantics).
        """
        url = (
            f"{self._restate_admin_url}/NdmoDocumentIngestionWorkflow/"
            f"{document_id}/send"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={
                    "object_name": minio_key,
                    "document_id": str(document_id),
                    "tenant_id": tenant_id,
                },
            )
            resp.raise_for_status()


def get_document_service() -> DocumentService:
    return DocumentService()
