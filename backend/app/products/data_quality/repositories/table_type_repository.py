from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class TableTypeRepository(PostgresqlAsyncRepository):
    """Persistence for t_dq_table_types — DQ team's per-table semantic typing."""

    async def find_by_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT id, tenant_id, connection_id, schema_name, table_name,
                      semantic_type, note, assigned_by, assigned_at, updated_at
               FROM dq.t_dq_table_types
               WHERE tenant_id = $1
               ORDER BY connection_id, schema_name, table_name""",
            (tenant_id,),
        )

    async def find_by_connection(self, connection_id: UUID, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT id, tenant_id, connection_id, schema_name, table_name,
                      semantic_type, note, assigned_by, assigned_at, updated_at
               FROM dq.t_dq_table_types
               WHERE connection_id = $1 AND tenant_id = $2
               ORDER BY schema_name, table_name""",
            (connection_id, tenant_id),
        )

    async def find_one(
        self, connection_id: UUID, schema_name: str, table_name: str, tenant_id: int
    ) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_table_types
               WHERE connection_id = $1 AND schema_name = $2
                 AND table_name = $3 AND tenant_id = $4""",
            (connection_id, schema_name, table_name, tenant_id),
        )

    async def upsert(
        self, tenant_id: int, connection_id: UUID, schema_name: str, table_name: str,
        semantic_type: str, note: str | None, assigned_by: int,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_table_types
                   (tenant_id, connection_id, schema_name, table_name,
                    semantic_type, note, assigned_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (connection_id, schema_name, table_name) DO UPDATE
                   SET semantic_type = EXCLUDED.semantic_type,
                       note          = EXCLUDED.note,
                       assigned_by   = EXCLUDED.assigned_by,
                       updated_at    = CURRENT_TIMESTAMP
               RETURNING *""",
            (tenant_id, connection_id, schema_name, table_name,
             semantic_type, note, assigned_by),
        )

    async def delete(self, connection_id: UUID, schema_name: str, table_name: str,
                     tenant_id: int) -> str:
        return await self._execute(
            """DELETE FROM dq.t_dq_table_types
               WHERE connection_id = $1 AND schema_name = $2
                 AND table_name = $3 AND tenant_id = $4""",
            (connection_id, schema_name, table_name, tenant_id),
        )
