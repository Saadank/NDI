from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class PickupTokenRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, share_request_id: UUID, contact_id: int,
                     token_hash: str, expires_at, max_downloads: int, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_pickup_tokens
               (tenant_id, share_request_id, contact_id, token_hash, expires_at, max_downloads, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            (tenant_id, share_request_id, contact_id, token_hash, expires_at, max_downloads, created_by),
        )

    async def find_by_token_hash(self, token_hash: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_pickup_tokens WHERE token_hash = $1",
            (token_hash,),
        )

    async def find_by_id(self, token_id: UUID) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_pickup_tokens WHERE id = $1",
            (token_id,),
        )

    async def list_by_request(self, share_request_id: UUID) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_pickup_tokens WHERE share_request_id = $1 ORDER BY created_at DESC",
            (share_request_id,),
        )

    async def list_by_recipient(self, recipient_id: int, active_only: bool = True) -> list[dict]:
        query = (
            """SELECT t.* FROM t_pickup_tokens t
               JOIN t_recipient_contacts c ON c.id = t.contact_id
               WHERE c.recipient_id = $1"""
        )
        if active_only:
            query += " AND t.revoked_at IS NULL AND t.expires_at > CURRENT_TIMESTAMP"
        query += " ORDER BY t.created_at DESC"
        return await self._fetch_all(query, (recipient_id,))

    async def mark_opened(self, token_id: UUID) -> dict:
        return await self._fetch_row(
            """UPDATE t_pickup_tokens
               SET first_opened_at = COALESCE(first_opened_at, CURRENT_TIMESTAMP)
               WHERE id = $1 RETURNING *""",
            (token_id,),
        )

    async def record_dpa(self, token_id: UUID, ip: str | None, user_agent: str | None) -> dict:
        return await self._fetch_row(
            """UPDATE t_pickup_tokens
               SET dpa_accepted_at = COALESCE(dpa_accepted_at, CURRENT_TIMESTAMP),
                   dpa_ip = COALESCE(dpa_ip, $2::inet),
                   dpa_user_agent = COALESCE(dpa_user_agent, $3)
               WHERE id = $1 RETURNING *""",
            (token_id, ip, user_agent),
        )

    async def increment_download(self, token_id: UUID) -> dict | None:
        # Atomic gate: only increments if token is not revoked/expired/exhausted.
        return await self._fetch_row_optional(
            """UPDATE t_pickup_tokens
               SET download_count = download_count + 1
               WHERE id = $1
                 AND download_count < max_downloads
                 AND revoked_at IS NULL
                 AND expires_at > CURRENT_TIMESTAMP
               RETURNING *""",
            (token_id,),
        )

    async def revoke(self, token_id: UUID, revoked_by: int, reason: str | None) -> dict:
        return await self._fetch_row(
            """UPDATE t_pickup_tokens
               SET revoked_at = CURRENT_TIMESTAMP,
                   revoked_by = $2,
                   revoke_reason = $3
               WHERE id = $1 AND revoked_at IS NULL
               RETURNING *""",
            (token_id, revoked_by, reason),
        )
