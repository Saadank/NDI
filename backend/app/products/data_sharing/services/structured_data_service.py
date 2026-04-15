"""
Structured data sharing: run a query (built from user-picked tables/columns or
a custom SQL string) against a registered connection, preview rows, or execute
the full result and attach the CSV to a share request as a t_files row.
"""
import csv
import hashlib
import io
import logging
import re
import uuid
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.gateways.object_store_gateway import ObjectStoreGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.permissions import (
    can_browse_connections, can_view_request, require,
)
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.products.data_sharing.repositories.file_repository import FileRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.timezone import now

logger = logging.getLogger(__name__)

# Only allow SELECT/WITH statements; reject anything with a statement terminator or DDL/DML.
_ALLOWED_SQL_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_DISALLOWED_TOKENS = re.compile(
    r"\b(insert|update|delete|drop|truncate|alter|create|grant|revoke|merge|call|exec|execute)\b",
    re.IGNORECASE,
)
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_custom_sql(sql: str) -> str:
    sql = (sql or "").strip()
    if not sql:
        raise ValidationException("SQL cannot be empty")
    if ";" in sql.rstrip(";"):
        raise ValidationException("SQL must be a single statement — no semicolons")
    if not _ALLOWED_SQL_START.match(sql):
        raise ValidationException("Only SELECT / WITH queries are allowed")
    if _DISALLOWED_TOKENS.search(sql):
        raise ValidationException("SQL contains disallowed keywords (write/DDL not permitted)")
    return sql.rstrip(";")


def _quote_ident(name: str) -> str:
    """Whitelist-style identifier quoting: reject anything that isn't a plain identifier."""
    if not _IDENT_RE.match(name or ""):
        raise ValidationException(f"Invalid identifier: {name!r}")
    return f'"{name}"'


def _build_sql_from_selection(selected_items: list[dict]) -> str:
    """
    selected_items is a list of {schema?, table, columns: [..]}.
    Produces a UNION ALL over the tables in simple form; each table is a separate
    SELECT so the user can pick subsets per table. For now we only emit the first
    item if more than one is present — downstream we can extend to per-table CSVs.
    """
    if not selected_items:
        raise ValidationException("At least one table selection is required")
    # Build one SELECT per table; callers today export only the first.
    item = selected_items[0]
    table = item.get("table")
    schema = item.get("schema")
    columns = item.get("columns") or []
    if not table:
        raise ValidationException("Table name is required in selection")
    if not columns:
        raise ValidationException(f"At least one column must be selected for table {table}")
    col_list = ", ".join(_quote_ident(c) for c in columns)
    table_ref = f"{_quote_ident(schema)}.{_quote_ident(table)}" if schema else _quote_ident(table)
    return f"SELECT {col_list} FROM {table_ref}"


class StructuredDataService:

    def __init__(self) -> None:
        self.conn_repo = ConnectionRepository()
        self.file_repo = FileRepository()
        self.request_repo = ShareRequestRepository()
        self.object_store = ObjectStoreGateway()
        self.audit = AuditService()

    def build_sql(self, selection_mode: str, selected_items, custom_sql) -> str:
        if selection_mode == "query":
            return _validate_custom_sql(custom_sql or "")
        if selection_mode == "tables":
            return _build_sql_from_selection(selected_items or [])
        raise ValidationException("selection_mode must be 'tables' or 'query'")

    async def _load_gateway(self, connection_id: UUID, tenant_id: int) -> DbConnectorGateway:
        conn = await self.conn_repo.find_by_id(connection_id, tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")
        return DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database", "") or "",
        )

    async def preview(
        self, connection_id: UUID, selection_mode: str, selected_items,
        custom_sql: str | None, auth_user: AuthUser, limit: int = 100,
    ) -> dict:
        require(can_browse_connections(auth_user), "You cannot preview data")
        sql = self.build_sql(selection_mode, selected_items, custom_sql)

        gateway = await self._load_gateway(connection_id, auth_user.tenant_id)
        try:
            result = await gateway.execute_query(sql, limit=limit)
        finally:
            await gateway.close()

        if not result.success:
            raise ValidationException(f"Query failed: {result.error}")

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="structured.previewed",
            resource_type="connection", resource_id=str(connection_id),
            actor_id=auth_user.user_id,
            metadata={"selection_mode": selection_mode, "row_count": len(result.data["rows"])},
        )
        return {
            "columns": result.data["columns"],
            "rows": result.data["rows"],
            "sql": sql,
        }

    async def attach_to_request(
        self, request_id: UUID, connection_id: UUID, selection_mode: str,
        selected_items, custom_sql: str | None, filename: str | None,
        auth_user: AuthUser,
    ) -> dict:
        """Run the full query, write CSV to MinIO, create a t_files row for this request."""
        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        if not request:
            raise ResourceNotFoundException("Request not found")
        require(can_view_request(auth_user, request), "You do not have access to this request")
        if request["status"] not in ("draft", "submitted", "in_review", "approved"):
            raise ValidationException("Request is not in a state that allows attaching data")

        sql = self.build_sql(selection_mode, selected_items, custom_sql)

        # Execute the full query
        gateway = await self._load_gateway(connection_id, auth_user.tenant_id)
        try:
            result = await gateway.execute_query(sql, limit=None)
        finally:
            await gateway.close()
        if not result.success:
            raise ValidationException(f"Query failed: {result.error}")

        # Write CSV to memory
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(result.data["columns"])
        for row in result.data["rows"]:
            writer.writerow(["" if v is None else v for v in row])
        csv_bytes = buf.getvalue().encode("utf-8")
        size = len(csv_bytes)
        sha256 = hashlib.sha256(csv_bytes).hexdigest()

        # Upload to MinIO
        storage_key = f"{auth_user.tenant_id}/{request_id}/{uuid.uuid4()}.csv"
        self.object_store.put_object(
            key=storage_key, data=csv_bytes, size=size, content_type="text/csv",
        )

        # Create t_files row (already 'uploaded' because we just wrote it)
        safe_name = filename or f"query_result_{request['request_number']}.csv"
        if not safe_name.lower().endswith(".csv"):
            safe_name += ".csv"
        file_record = await self.file_repo.create(
            request_id=request_id, tenant_id=auth_user.tenant_id,
            original_filename=safe_name, storage_key=storage_key,
            file_size_bytes=size, mime_type="text/csv", sha256_hash=sha256,
            uploaded_by=auth_user.user_id,
        )
        file_record = await self.file_repo.update_status(
            file_record["id"], "uploaded", uploaded_at=now(),
        )

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="structured.extracted",
            resource_type="file", resource_id=str(file_record["id"]),
            actor_id=auth_user.user_id, request_id=request_id,
            metadata={
                "connection_id": str(connection_id),
                "selection_mode": selection_mode,
                "row_count": len(result.data["rows"]),
                "size_bytes": size,
            },
        )
        return {
            "file": file_record,
            "row_count": len(result.data["rows"]),
            "column_count": len(result.data["columns"]),
        }


def get_structured_data_service() -> StructuredDataService:
    return StructuredDataService()
