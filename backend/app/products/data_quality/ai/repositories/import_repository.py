"""Persistence for dq.t_dq_imports — Excel upload lifecycle.

State machine: uploaded -> parsing -> enriching -> awaiting_review
-> applied. Two terminal escapes: error (parse/enrich failed) and
rolled_back (admin reverted an applied import).
"""
import json
from datetime import datetime

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ImportRepository(PostgresqlAsyncRepository):

    async def insert(
        self, *, tenant_id: int, uploader_id: int, kind: str,
        filename: str, file_hash: str, version_label: str | None,
    ) -> dict:
        """Create a fresh import row. UNIQUE(tenant_id, file_hash) means the
        caller should catch the unique-violation and return the existing
        row in that case (handled in the service layer)."""
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_imports
                  (tenant_id, uploader_id, kind, filename, file_hash,
                   status, version_label)
               VALUES ($1, $2, $3, $4, $5, 'uploaded', $6)
               RETURNING *""",
            (tenant_id, uploader_id, kind, filename, file_hash, version_label),
        )

    async def find_by_id(self, import_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_imports
                WHERE id = $1 AND tenant_id = $2""",
            (import_id, tenant_id),
        )

    async def find_by_hash(self, tenant_id: int, file_hash: str) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_imports
                WHERE tenant_id = $1 AND file_hash = $2""",
            (tenant_id, file_hash),
        )

    async def list_for_tenant(
        self, tenant_id: int, *,
        kind: str | None = None, status: str | None = None,
    ) -> list[dict]:
        sql = ["SELECT * FROM dq.t_dq_imports WHERE tenant_id = $1"]
        args: list = [tenant_id]
        if kind:
            args.append(kind)
            sql.append(f"AND kind = ${len(args)}")
        if status:
            args.append(status)
            sql.append(f"AND status = ${len(args)}")
        sql.append("ORDER BY created_at DESC")
        return await self._fetch_all(" ".join(sql), tuple(args))

    async def update_status(
        self, import_id: int, tenant_id: int, status: str, *,
        row_count: int | None = None, error_count: int | None = None,
        errors: list | None = None,
        applied_at: datetime | None = None,
        rolled_back_at: datetime | None = None,
    ) -> dict:
        """Patch — only fields that are not None get written."""
        # Build a dynamic SET clause so we don't clobber columns we didn't
        # mean to touch (a CASE-WHEN approach would be busier here).
        sets = ["status = $3"]
        args: list = [import_id, tenant_id, status]
        if row_count is not None:
            args.append(row_count); sets.append(f"row_count = ${len(args)}")
        if error_count is not None:
            args.append(error_count); sets.append(f"error_count = ${len(args)}")
        if errors is not None:
            args.append(json.dumps(errors)); sets.append(f"errors = ${len(args)}::jsonb")
        if applied_at is not None:
            args.append(applied_at); sets.append(f"applied_at = ${len(args)}")
        if rolled_back_at is not None:
            args.append(rolled_back_at); sets.append(f"rolled_back_at = ${len(args)}")
        sql = (
            "UPDATE dq.t_dq_imports SET " + ", ".join(sets)
            + " WHERE id = $1 AND tenant_id = $2 RETURNING *"
        )
        return await self._fetch_row(sql, tuple(args))
