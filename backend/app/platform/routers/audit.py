from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.platform.services.audit_service import AuditService, get_audit_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/")
async def list_audit_events(
    page: int = 1,
    limit: int = 20,
    request_id: UUID | None = None,
    actor_id: int | None = None,
    action_type: str | None = None,
    auth_user: AuthUser = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    return await service.list_events(
        tenant_id=auth_user.tenant_id, page=page, limit=limit,
        request_id=request_id, actor_id=actor_id, action_type=action_type,
    )
