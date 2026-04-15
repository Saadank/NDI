import logging
from uuid import UUID

from app.products.data_sharing.permissions import (
    can_browse_schemas, can_manage_schemas, require,
)
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


class SchemaService(PostgresqlAsyncRepository):

    async def get_schema(self, connection_id: UUID, auth_user: AuthUser) -> dict | None:
        require(can_manage_schemas(auth_user), "Only admins can manage schemas")
        return await self._fetch_row_optional(
            "SELECT * FROM t_schemas WHERE connection_id = $1 AND tenant_id = $2",
            (connection_id, auth_user.tenant_id),
        )

    async def browse_schema(self, connection_id: UUID, auth_user: AuthUser) -> dict:
        """Requester-visible schema: read cached JSONB, or introspect on demand."""
        require(can_browse_schemas(auth_user), "You cannot browse schemas")
        row = await self._fetch_row_optional(
            "SELECT schema_data FROM t_schemas WHERE connection_id = $1 AND tenant_id = $2",
            (connection_id, auth_user.tenant_id),
        )
        if row and row.get("schema_data"):
            return {"connection_id": str(connection_id), "schema_data": row["schema_data"]}

        # Not cached — introspect live
        conn_repo = ConnectionRepository()
        conn = await conn_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        from app.gateways.db_connector_gateway import DbConnectorGateway
        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database", "") or "",
        )
        try:
            result = await gateway.list_schemas()
        finally:
            await gateway.close()

        if not result.success:
            from app.utils.exceptions import ValidationException
            raise ValidationException(f"Failed to introspect schema: {result.error}")

        await self.save_schema(connection_id, auth_user.tenant_id, result.data)
        return {"connection_id": str(connection_id), "schema_data": result.data}

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
