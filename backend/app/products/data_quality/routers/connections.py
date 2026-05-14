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
