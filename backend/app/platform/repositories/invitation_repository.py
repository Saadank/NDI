from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class InvitationRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, email: str, role: str, product_slug: str | None, product_role: str | None, token: str, invited_by: int, expires_at) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_invitations (tenant_id, email, role, product_slug, product_role, token, invited_by, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *""",
            (tenant_id, email, role, product_slug, product_role, token, invited_by, expires_at),
        )

    async def find_by_token(self, token: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_invitations WHERE token = $1", (token,)
        )

    async def find_by_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_invitations WHERE tenant_id = $1 ORDER BY created_at DESC", (tenant_id,)
        )

    async def update_status(self, invitation_id: int, status: str) -> dict:
        query = "UPDATE t_invitations SET status = $1"
        if status == "accepted":
            query += ", accepted_at = CURRENT_TIMESTAMP"
        query += " WHERE id = $2 RETURNING *"
        return await self._fetch_row(query, (status, invitation_id))
