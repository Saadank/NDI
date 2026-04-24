from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.core.security import get_current_user
from app.platform.services.audit_export_service import AuditExportService, get_audit_export_service
from app.platform.services.audit_service import AuditService, get_audit_service
from app.products.data_sharing.permissions import can_view_audit_logs, require
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
    require(can_view_audit_logs(auth_user), "Only DPO and org admins can view audit events")
    return await service.list_events(
        tenant_id=auth_user.tenant_id, page=page, limit=limit,
        request_id=request_id, actor_id=actor_id, action_type=action_type,
    )


@router.get("/export")
async def export_audit_events(
    request_id: UUID | None = None,
    actor_id: int | None = None,
    action_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    auth_user: AuthUser = Depends(get_current_user),
    service: AuditExportService = Depends(get_audit_export_service),
):
    """Export the filtered audit trail as CSV (BRD §2.2, EC-21).

    The export action is itself logged. When the results include personal
    data, the file is auto-classified Confidential and the Org Admin is
    notified. Classification and row count are returned as response headers so
    the caller can react without opening the body.
    """
    csv_body, manifest = await service.export_csv(
        auth_user=auth_user, request_id=request_id, actor_id=actor_id,
        action_type=action_type, from_date=from_date, to_date=to_date,
    )
    filename = f"audit-{manifest['export_id']}.csv"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Audit-Export-Id": manifest["export_id"],
        "X-Audit-Export-Classification": manifest["classification"],
        "X-Audit-Export-Row-Count": str(manifest["row_count"]),
        "X-Audit-Export-Contains-PII": str(manifest["contains_personal_data"]).lower(),
    }
    return Response(content=csv_body, media_type="text/csv", headers=headers)
