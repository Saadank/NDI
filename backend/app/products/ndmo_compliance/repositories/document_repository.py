"""DocumentRepository — async CRUD on ndmo.t_ndmo_documents.

Datarix-Mono convention (cf. data_sharing/data_quality repositories): every
query takes ``tenant_id`` explicitly and includes it in the WHERE clause.
This product does NOT use Postgres per-tenant schemas (cortex pattern);
isolation is enforced at the SQL level instead.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.products.ndmo_compliance.entities.document import Document
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


class DocumentRepository(PostgresqlAsyncRepository):
    """All access to ndmo.t_ndmo_documents."""

    async def create(self, *, tenant_id: int, file_name: str, minio_key: str,
                     mime_type: str | None, size_bytes: int | None,
                     uploaded_by: int, cycle_id: int | None) -> Document:
        row = await self._fetch_row(
            """
            INSERT INTO ndmo.t_ndmo_documents
                (tenant_id, cycle_id, file_name, minio_key, mime_type, size_bytes,
                 status, uploaded_by)
            VALUES ($1, $2, $3, $4, $5, $6, 'uploaded', $7)
            RETURNING id, tenant_id, cycle_id, file_name, minio_key, mime_type,
                      size_bytes, status, uploaded_by, uploaded_at, page_count,
                      sha256, processed_at
            """,
            (tenant_id, cycle_id, file_name, minio_key, mime_type, size_bytes, uploaded_by),
        )
        return self._row_to_entity(row)

    async def find_by_id(self, *, document_id: UUID, tenant_id: int) -> Document:
        row = await self._fetch_row(
            """
            SELECT id, tenant_id, cycle_id, file_name, minio_key, mime_type,
                   size_bytes, status, uploaded_by, uploaded_at, page_count,
                   sha256, processed_at
              FROM ndmo.t_ndmo_documents
             WHERE id = $1 AND tenant_id = $2
            """,
            (document_id, tenant_id),
        )
        return self._row_to_entity(row)

    async def update_status(self, *, document_id: UUID, tenant_id: int,
                            status: DocumentStatus) -> None:
        await self._execute(
            """
            UPDATE ndmo.t_ndmo_documents
               SET status = $1
             WHERE id = $2 AND tenant_id = $3
            """,
            (status.value, document_id, tenant_id),
        )

    async def update_after_extraction(self, *, document_id: UUID, tenant_id: int,
                                       page_count: int, sha256: str | None) -> None:
        await self._execute(
            """
            UPDATE ndmo.t_ndmo_documents
               SET page_count = $1,
                   sha256 = COALESCE($2, sha256),
                   status = 'extracting'
             WHERE id = $3 AND tenant_id = $4
            """,
            (page_count, sha256, document_id, tenant_id),
        )

    async def mark_processed(self, *, document_id: UUID, tenant_id: int) -> None:
        await self._execute(
            """
            UPDATE ndmo.t_ndmo_documents
               SET status = 'ready',
                   processed_at = CURRENT_TIMESTAMP
             WHERE id = $1 AND tenant_id = $2
            """,
            (document_id, tenant_id),
        )

    async def list_by_tenant(self, *, tenant_id: int, cycle_id: int | None = None,
                              limit: int = 100, offset: int = 0) -> list[Document]:
        if cycle_id is None:
            rows = await self._fetch_all(
                """
                SELECT id, tenant_id, cycle_id, file_name, minio_key, mime_type,
                       size_bytes, status, uploaded_by, uploaded_at, page_count,
                       sha256, processed_at
                  FROM ndmo.t_ndmo_documents
                 WHERE tenant_id = $1
                 ORDER BY uploaded_at DESC
                 LIMIT $2 OFFSET $3
                """,
                (tenant_id, limit, offset),
            )
        else:
            rows = await self._fetch_all(
                """
                SELECT id, tenant_id, cycle_id, file_name, minio_key, mime_type,
                       size_bytes, status, uploaded_by, uploaded_at, page_count,
                       sha256, processed_at
                  FROM ndmo.t_ndmo_documents
                 WHERE tenant_id = $1 AND cycle_id = $2
                 ORDER BY uploaded_at DESC
                 LIMIT $3 OFFSET $4
                """,
                (tenant_id, cycle_id, limit, offset),
            )
        return [self._row_to_entity(r) for r in rows]

    @staticmethod
    def _row_to_entity(row: dict) -> Document:
        return Document(
            id=row["id"],
            tenant_id=row["tenant_id"],
            cycle_id=row.get("cycle_id"),
            file_name=row["file_name"],
            minio_key=row["minio_key"],
            mime_type=row.get("mime_type"),
            size_bytes=row.get("size_bytes"),
            status=DocumentStatus(row["status"]),
            uploaded_by=row["uploaded_by"],
            uploaded_at=row["uploaded_at"],
            page_count=row.get("page_count"),
            sha256=row.get("sha256"),
            processed_at=row.get("processed_at"),
        )
