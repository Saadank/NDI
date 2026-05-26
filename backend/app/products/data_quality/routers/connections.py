"""Read-only connection listing scoped to the Data Quality product.

DQ reuses the data_sharing source-DB connections (same t_connections table)
but exposes them under its own permission gate (can_use_dq) so the DQ UI
doesn't have to depend on data_sharing's stricter listing rules.
"""
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_sharing.repositories.connection_repository import ConnectionRepository
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/connections", tags=["dq-connections"])


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
