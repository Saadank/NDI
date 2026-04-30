"""Table-listing + semantic-typing for the Data Quality product.

BRD §4.2 / FR-TYPE: every source table eligible for DQ scanning carries a
semantic type (master_data, transaction, event_log, reference, staging,
snapshot). The type drives rule applicability — e.g. uniqueness rules are
suppressed on entity columns of event_log tables.

This service combines the live source-DB table list (via the existing
DbConnectorGateway) with the team's persisted assignments (t_dq_table_types)
so the UI can show a single merged list.
"""
import logging
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.table_type_repository import TableTypeRepository
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

# Each connector exposes tables in a single default schema. Listing with
# explicit per-schema discovery is deferred to a later step; for now we tag
# whatever the gateway returns with the conventional default for its db_type.
_DEFAULT_SCHEMA_BY_DB_TYPE = {
    "postgresql": "public",
    "mysql": None,        # the DB name acts as the schema
    "mariadb": None,
    "mssql": "dbo",
    "oracle": None,       # the username acts as the schema
    "clickhouse": "default",
}

_VALID_TYPES = {"master_data", "transaction", "event_log",
                "reference", "staging", "snapshot"}


class TableTypeService:

    def __init__(self) -> None:
        self.repo = TableTypeRepository()
        self.connection_repo = ConnectionRepository()

    async def preview_table(
        self, connection_id: UUID, schema_name: str, table_name: str,
        limit: int, auth_user: AuthUser,
    ) -> dict:
        """Live peek at a source table — returns column metadata plus a small
        sample of rows. **Nothing is persisted** (BRD: metadata-only DQ store).
        The sample is fetched on each request so the user can sanity-check the
        data without leaking it into our schema."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if limit < 1 or limit > 100:
            raise ValidationException("limit must be between 1 and 100")

        conn = await self.connection_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        # Lazy-import to avoid a circular dep at module load.
        from app.products.data_quality.services.profiler_service import (
            _qualified_table, _quote_ident,
        )

        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        try:
            db_type = conn["db_type"]
            qtable = _qualified_table(db_type, schema_name, table_name)

            # Column metadata via information_schema (or the dialect equivalent).
            if db_type in ("postgresql", "mysql", "mariadb", "mssql"):
                col_sql = (
                    "SELECT column_name, data_type, is_nullable, ordinal_position "
                    "FROM information_schema.columns "
                    f"WHERE table_schema = '{schema_name}' AND table_name = '{table_name}' "
                    "ORDER BY ordinal_position"
                )
            elif db_type == "oracle":
                col_sql = (
                    "SELECT column_name, data_type, nullable AS is_nullable, column_id AS ordinal_position "
                    "FROM all_tab_columns "
                    f"WHERE owner = '{schema_name.upper()}' AND table_name = '{table_name.upper()}' "
                    "ORDER BY column_id"
                )
            elif db_type == "clickhouse":
                col_sql = (
                    "SELECT name AS column_name, type AS data_type, "
                    "if(type LIKE 'Nullable%','YES','NO') AS is_nullable, "
                    "position AS ordinal_position "
                    f"FROM system.columns WHERE database = '{schema_name}' AND table = '{table_name}' "
                    "ORDER BY position"
                )
            else:
                raise ValidationException(f"Preview unsupported on {db_type}")

            cols_res = await gateway.execute_query(col_sql)
            if not cols_res.success:
                return {"columns": [], "rows": [], "error": cols_res.error}
            columns = [
                {
                    "name": row[0], "data_type": row[1],
                    "nullable": str(row[2]).upper() in ("YES", "Y", "1"),
                    "ordinal": row[3],
                }
                for row in (cols_res.data or {}).get("rows", [])
            ]

            # Live sample — wrapped in a LIMIT so we never pull the whole table.
            sample_sql = self._sample_sql(db_type, qtable, limit)
            data_res = await gateway.execute_query(sample_sql)
            if not data_res.success:
                return {"columns": columns, "rows": [], "error": data_res.error}

            return {
                "schema_name": schema_name,
                "table_name": table_name,
                "db_type": db_type,
                "columns": columns,
                "row_columns": (data_res.data or {}).get("columns", []),
                "rows": (data_res.data or {}).get("rows", []),
                "limit": limit,
            }
        finally:
            await gateway.close()

    @staticmethod
    def _sample_sql(db_type: str, qtable: str, limit: int) -> str:
        if db_type == "mssql":
            return f"SELECT TOP {limit} * FROM {qtable}"
        if db_type == "oracle":
            return f"SELECT * FROM {qtable} FETCH FIRST {limit} ROWS ONLY"
        return f"SELECT * FROM {qtable} LIMIT {limit}"

    async def list_tables_with_types(self, connection_id: UUID, auth_user: AuthUser) -> dict:
        """For one connection, return live table list joined with stored types."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        conn = await self.connection_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        schema_name = (
            _DEFAULT_SCHEMA_BY_DB_TYPE.get(conn["db_type"])
            or conn.get("database")
            or conn.get("username")
            or "default"
        )

        live_tables: list[str] = []
        gw_error: str | None = None
        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        try:
            result = await gateway.list_tables()
            if result.success:
                live_tables = result.data or []
            else:
                gw_error = result.error
                logger.warning("list_tables failed for connection %s: %s", connection_id, result.error)
        finally:
            await gateway.close()

        stored = await self.repo.find_by_connection(connection_id, auth_user.tenant_id)
        type_index: dict[tuple[str, str], dict] = {
            (row["schema_name"], row["table_name"]): row for row in stored
        }

        items: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for tname in live_tables:
            key = (schema_name, tname)
            seen.add(key)
            row = type_index.get(key)
            items.append({
                "schema_name": schema_name,
                "table_name": tname,
                "semantic_type": row["semantic_type"] if row else None,
                "note": row["note"] if row else None,
                "assigned_by": row["assigned_by"] if row else None,
                "assigned_at": row["assigned_at"] if row else None,
                "low_context_confidence": row is None,  # FR-TYPE-02 badge
                "live": True,
            })

        # Stored assignments for tables that are no longer present in the live
        # source — surface them so the team can clean them up.
        for (sch, tbl), row in type_index.items():
            if (sch, tbl) in seen:
                continue
            items.append({
                "schema_name": sch,
                "table_name": tbl,
                "semantic_type": row["semantic_type"],
                "note": row["note"],
                "assigned_by": row["assigned_by"],
                "assigned_at": row["assigned_at"],
                "low_context_confidence": False,
                "live": False,
            })

        return {
            "connection_id": str(connection_id),
            "db_type": conn["db_type"],
            "default_schema": schema_name,
            "source_error": gw_error,
            "items": items,
        }

    async def assign(
        self, connection_id: UUID, schema_name: str, table_name: str,
        semantic_type: str, note: str | None, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        if semantic_type not in _VALID_TYPES:
            raise ValidationException(
                f"semantic_type must be one of {sorted(_VALID_TYPES)}"
            )
        if not schema_name or not table_name:
            raise ValidationException("schema_name and table_name are required")

        # Confirm the connection belongs to the caller's tenant before writing.
        conn = await self.connection_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        return await self.repo.upsert(
            tenant_id=auth_user.tenant_id,
            connection_id=connection_id,
            schema_name=schema_name,
            table_name=table_name,
            semantic_type=semantic_type,
            note=note,
            assigned_by=auth_user.user_id,
        )

    async def clear(
        self, connection_id: UUID, schema_name: str, table_name: str, auth_user: AuthUser,
    ) -> None:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        # Guard tenant scope on delete too.
        conn = await self.connection_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")
        await self.repo.delete(connection_id, schema_name, table_name, auth_user.tenant_id)


def get_table_type_service() -> TableTypeService:
    return TableTypeService()
