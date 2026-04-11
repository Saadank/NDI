import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class SchemaService(PostgresqlAsyncRepository):

    async def get_schema(self, connection_id: UUID, auth_user: AuthUser) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_schemas WHERE connection_id = $1 AND tenant_id = $2",
            (connection_id, auth_user.tenant_id),
        )

    async def save_schema(self, connection_id: UUID, tenant_id: int, schema_data: dict) -> dict:
        import json
        existing = await self._fetch_row_optional(
            "SELECT * FROM t_schemas WHERE connection_id = $1 AND tenant_id = $2",
            (connection_id, tenant_id),
        )
        if existing:
            return await self._fetch_row(
                "UPDATE t_schemas SET schema_data = $1::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *",
                (json.dumps(schema_data), existing["id"]),
            )
        return await self._fetch_row(
            "INSERT INTO t_schemas (connection_id, tenant_id, schema_data) VALUES ($1, $2, $3::jsonb) RETURNING *",
            (connection_id, tenant_id, json.dumps(schema_data)),
        )


def get_schema_service() -> SchemaService:
    return SchemaService()
