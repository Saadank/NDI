from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class FileRepository(PostgresqlAsyncRepository):

    async def create(self, request_id: UUID, tenant_id: int, original_filename: str,
                     storage_key: str, file_size_bytes: int, mime_type: str | None,
                     sha256_hash: str, uploaded_by: int | None, expires_at=None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_files (request_id, tenant_id, original_filename, storage_key,
               file_size_bytes, mime_type, sha256_hash, uploaded_by, expires_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
            (request_id, tenant_id, original_filename, storage_key, file_size_bytes, mime_type, sha256_hash, uploaded_by, expires_at),
        )

    async def find_by_id(self, file_id: UUID) -> dict:
        return await self._fetch_row("SELECT * FROM t_files WHERE id = $1", (file_id,))

    async def find_by_request(self, request_id: UUID) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_files WHERE request_id = $1 AND deleted_at IS NULL ORDER BY created_at", (request_id,)
        )

    async def update_status(self, file_id: UUID, status: str, **extra) -> dict:
        set_parts = ["status = $1"]
        args: list = [status]
        idx = 2
        for key, val in extra.items():
            set_parts.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        args.append(file_id)
        return await self._fetch_row(
            f"UPDATE t_files SET {', '.join(set_parts)} WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

    async def find_expired_files(self) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_files WHERE expires_at < CURRENT_TIMESTAMP AND status = 'uploaded'"
        )

    async def find_files_expiring_within(self, hours: int) -> list[dict]:
        """Files that expire in <= `hours` hours and have not yet been warned
        (BRD §3.7 48-hour notice)."""
        # Build the interval as an explicit make_interval() call so asyncpg
        # can bind the int cleanly.
        return await self._fetch_all(
            "SELECT * FROM t_files "
            "WHERE status = 'uploaded' "
            "AND pre_expiry_notified_at IS NULL "
            "AND expires_at IS NOT NULL "
            "AND expires_at BETWEEN CURRENT_TIMESTAMP "
            "AND CURRENT_TIMESTAMP + make_interval(hours => $1)",
            (hours,),
        )

    async def mark_pre_expiry_notified(self, file_id: UUID) -> None:
        await self._execute(
            "UPDATE t_files SET pre_expiry_notified_at = CURRENT_TIMESTAMP WHERE id = $1",
            (file_id,),
        )

    async def soft_delete(self, file_id: UUID, reason: str) -> dict:
        return await self._fetch_row(
            "UPDATE t_files SET deleted_at = CURRENT_TIMESTAMP, deletion_reason = $1, status = 'deleted' WHERE id = $2 RETURNING *",
            (reason, file_id),
        )

    async def total_bytes_for_tenant(self, tenant_id: int) -> int:
        value = await self._fetch_value(
            "SELECT COALESCE(SUM(file_size_bytes), 0) FROM t_files "
            "WHERE tenant_id = $1 AND status = 'uploaded'",
            (tenant_id,),
        )
        return int(value or 0)
