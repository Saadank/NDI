"""Source-DB connection endpoints scoped to the Data Quality product.

DQ reuses the data_sharing source-DB connections table (``t_connections``)
but exposes its own CRUD under the DQ permission gate so DQ admins don't
have to ALSO carry the data_sharing admin entitlement just to add a source
to scan. The create / test routes call the shared ``ConnectionRepository``
directly, bypassing the data_sharing service layer (which gates on
``can_manage_connections``).
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ResourceNotFoundException, ValidationException


class _ConnectionProfileCounter(PostgresqlAsyncRepository):
    """Inline helper: count DQ profiles still pointing at a connection.

    A soft-delete on the connection would orphan these profiles (their
    connection_id ends up at a row with deleted_at != null), so the
    delete route refuses while any reference remains."""

    async def profiles_for_connection(
        self, connection_id, tenant_id: int,
    ) -> list[dict]:
        return await self._fetch_all(
            """SELECT id, name, location_path, schema_name, table_name
                 FROM dq.t_dq_profiles
                WHERE connection_id = $1 AND tenant_id = $2
             ORDER BY id""",
            (connection_id, tenant_id),
        )

router = APIRouter(prefix="/connections", tags=["dq-connections"])


# Mirror of data_sharing's CreateConnectionBody. Duplicated rather than
# imported so DQ stays decoupled from data_sharing's router module shape.
class CreateConnectionBody(BaseModel):
    db_type: str = Field(min_length=1, max_length=40)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database: str | None = Field(default=None, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=512)
    description: str | None = Field(default=None, max_length=500)


@router.get("/")
async def list_dq_connections(auth_user: AuthUser = Depends(get_current_user)):
    """List all (non-deleted) source-DB connections for the caller's tenant.
    Passwords are redacted on the way out — they are never needed by the UI."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    if not auth_user.tenant_id:
        return []
    repo = ConnectionRepository()
    rows = await repo.find_by_tenant(auth_user.tenant_id)
    return [
        {
            "id": str(r["id"]),
            "db_type": r["db_type"],
            "host": r["host"],
            "port": r["port"],
            "database": r.get("database"),
            "description": r.get("description"),
            "status": r.get("status"),
            "created_at": r.get("created_at"),
        }
        for r in rows
    ]


@router.post("/")
async def create_dq_connection(
    body: CreateConnectionBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Create a new source-DB connection under the DQ gate. Same row in
    ``t_connections`` data_sharing reads — both products share the table."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    repo = ConnectionRepository()
    row = await repo.create(
        tenant_id=auth_user.tenant_id,
        db_type=body.db_type, host=body.host, port=body.port,
        database=body.database, username=body.username,
        password_encrypted=body.password,
        description=body.description,
        created_by=auth_user.user_id,
    )
    return {
        "detail": "Connection created",
        "connection": {
            "id": str(row["id"]),
            "db_type": row["db_type"],
            "host": row["host"],
            "port": row["port"],
            "database": row.get("database"),
            "description": row.get("description"),
            "status": row.get("status"),
            "created_at": row.get("created_at"),
        },
    }


@router.delete("/{connection_id}")
async def delete_dq_connection(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Soft-delete (sets ``deleted_at``). Refuses with a precise list of
    blocking DQ profiles when any still reference the connection, so the
    user can clean them up first without trial-and-error.

    Why soft-delete: a hard DELETE on ``t_connections`` would CASCADE
    into ``t_dq_profiles``, ``t_dq_scans``, ``t_dq_active_rules``,
    ``t_dq_issues``, ``t_dq_column_profiles``, and ``t_dq_table_types``.
    Far too destructive for an everyday "remove this connection" action.
    Soft-delete + profile-refuse is the policy.
    """
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    repo = ConnectionRepository()
    conn = await repo.find_by_id(connection_id, auth_user.tenant_id)
    if not conn:
        raise ResourceNotFoundException("Connection not found")

    counter = _ConnectionProfileCounter()
    blockers = await counter.profiles_for_connection(
        connection_id, auth_user.tenant_id,
    )
    if blockers:
        # Surface the exact profiles so the user can navigate to and
        # delete each one. 400 keeps it client-side recoverable.
        raise ValidationException(
            "Connection has DQ profiles attached. Delete those first, then retry. "
            "Blocking profiles: "
            + ", ".join(
                f"#{p['id']} {p['name']} ({p['schema_name']}.{p['table_name']})"
                for p in blockers
            )
        )

    await repo.soft_delete(connection_id)
    return {
        "detail": "Connection deleted (soft — row preserved with deleted_at set)",
        "connection_id": str(connection_id),
    }


@router.post("/test-draft")
async def test_dq_connection_draft(
    body: CreateConnectionBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Test connection credentials without persisting a row.
    Accepts the same payload as create, opens a transient connection,
    returns {success, error}. Nothing is written to the database."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    gateway = DbConnectorGateway(
        db_type=body.db_type, username=body.username,
        password=body.password, host=body.host,
        port=str(body.port), database=body.database or "",
    )
    try:
        result = await gateway.test_connection()
        return {"success": result.success, "error": result.error}
    finally:
        await gateway.close()


@router.post("/{connection_id}/test")
async def test_dq_connection(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
):
    """Connectivity probe — opens a transient connection through the
    existing gateway, runs a no-op query, returns ``{success, error}``.
    Does NOT modify the row's status; that's the connector's own job."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    repo = ConnectionRepository()
    conn = await repo.find_by_id(connection_id, auth_user.tenant_id)
    if not conn:
        return {"success": False, "error": "Connection not found"}
    gateway = DbConnectorGateway(
        db_type=conn["db_type"], username=conn["username"],
        password=conn["password_encrypted"], host=conn["host"],
        port=str(conn["port"]), database=conn.get("database") or "",
    )
    try:
        result = await gateway.test_connection()
        return {"success": result.success, "error": result.error}
    finally:
        await gateway.close()
