from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ConnectionRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, db_type: str, host: str, port: int, database: str | None,
                     username: str, password_encrypted: str, description: str | None, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_connections (tenant_id, db_type, host, port, database, username, password_encrypted, description, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
            (tenant_id, db_type, host, port, database, username, password_encrypted, description, created_by),
        )

    async def find_by_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_connections WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC",
            (tenant_id,),
        )

    async def find_by_id(self, connection_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            "SELECT * FROM t_connections WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL",
            (connection_id, tenant_id),
        )

    async def soft_delete(self, connection_id: UUID) -> str:
        return await self._execute(
            "UPDATE t_connections SET deleted_at = CURRENT_TIMESTAMP WHERE id = $1", (connection_id,)
        )
