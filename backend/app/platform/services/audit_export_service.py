"""Audit export (BRD §2.2, EC-21).

The export itself is a first-class audit event. If any row in the export references
personal data, the resulting document is auto-classified as Confidential and both
the requester (DPO / Org Admin) and the system Org Admin are notified.
"""
import csv
import io
import json
import logging
from datetime import datetime
from uuid import UUID

from app.platform.repositories.user_repository import UserRepository
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.permissions import can_view_audit_logs
from app.products.data_sharing.services.notification_service import NotificationService
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ForbiddenException, ValidationException

logger = logging.getLogger(__name__)

_CSV_COLUMNS = [
    "id", "created_at", "tenant_id", "request_id", "actor_id",
    "actor_ip", "actor_user_agent", "action_type", "resource_type",
    "resource_id", "before_state", "after_state", "metadata",
]


class AuditExportService(PostgresqlAsyncRepository):

    def __init__(self) -> None:
        super().__init__()
        self.audit = AuditService()
        self.users = UserRepository()
        self.notifications = NotificationService()

    async def export_csv(
        self,
        auth_user: AuthUser,
        request_id: UUID | None = None,
        actor_id: int | None = None,
        action_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[str, dict]:
        """Return (csv_body, manifest). Manifest includes classification and row count."""
        if not can_view_audit_logs(auth_user):
            raise ForbiddenException("Only DPO and admins can export the audit trail")
        if from_date and to_date and from_date > to_date:
            raise ValidationException("from_date must be on or before to_date")

        rows = await self._fetch_rows(
            tenant_id=auth_user.tenant_id,
            request_id=request_id, actor_id=actor_id, action_type=action_type,
            from_date=from_date, to_date=to_date,
        )

        contains_pii = await self._contains_personal_data(rows, auth_user.tenant_id)
        classification = "confidential" if contains_pii else "internal"

        csv_body = self._rows_to_csv(rows)

        # Persist the export envelope and log the export action itself.
        export_row = await self._fetch_row(
            """INSERT INTO t_audit_exports
               (tenant_id, requested_by, format, filters, row_count,
                contains_personal_data, classification)
               VALUES ($1, $2, 'csv', $3::jsonb, $4, $5, $6) RETURNING *""",
            (
                auth_user.tenant_id,
                auth_user.user_id,
                json.dumps({
                    "request_id": str(request_id) if request_id else None,
                    "actor_id": actor_id,
                    "action_type": action_type,
                    "from_date": from_date.isoformat() if from_date else None,
                    "to_date": to_date.isoformat() if to_date else None,
                }),
                len(rows),
                contains_pii,
                classification,
            ),
        )

        await self.audit.log(
            tenant_id=auth_user.tenant_id,
            action_type="audit.exported",
            resource_type="audit_export",
            resource_id=str(export_row["id"]),
            actor_id=auth_user.user_id,
            metadata={
                "row_count": len(rows),
                "contains_personal_data": contains_pii,
                "classification": classification,
                "format": "csv",
            },
        )

        # BRD EC-21: notify the Org Admin when the export contains personal data.
        if contains_pii:
            admin = await self.users.find_first_org_admin(auth_user.tenant_id)
            if admin and admin["id"] != auth_user.user_id:
                await self.notifications.create_notification(
                    user_id=admin["id"],
                    tenant_id=auth_user.tenant_id,
                    type="audit_export_pii",
                    title=(
                        f"Audit export containing personal data downloaded "
                        f"({len(rows)} rows, classification=confidential)"
                    ),
                )

        manifest = {
            "export_id": str(export_row["id"]),
            "row_count": len(rows),
            "contains_personal_data": contains_pii,
            "classification": classification,
        }
        return csv_body, manifest

    async def _fetch_rows(
        self, *, tenant_id: int, request_id: UUID | None, actor_id: int | None,
        action_type: str | None, from_date: datetime | None, to_date: datetime | None,
    ) -> list[dict]:
        conds = ["tenant_id = $1"]
        args: list = [tenant_id]
        idx = 2
        if request_id:
            conds.append(f"request_id = ${idx}"); args.append(request_id); idx += 1
        if actor_id:
            conds.append(f"actor_id = ${idx}"); args.append(actor_id); idx += 1
        if action_type:
            conds.append(f"action_type = ${idx}"); args.append(action_type); idx += 1
        if from_date:
            conds.append(f"created_at >= ${idx}"); args.append(from_date); idx += 1
        if to_date:
            conds.append(f"created_at <= ${idx}"); args.append(to_date); idx += 1
        where = " AND ".join(conds)
        return await self._fetch_all(
            f"SELECT * FROM t_audit_events WHERE {where} ORDER BY created_at",
            tuple(args),
        )

    async def _contains_personal_data(self, rows: list[dict], tenant_id: int) -> bool:
        """Heuristic check — a row relates to personal data if either (a) its
        payload or metadata mentions personal data, or (b) it references a
        request whose `personal_data_involved` flag is true.
        """
        if not rows:
            return False
        request_ids = {r.get("request_id") for r in rows if r.get("request_id")}
        if request_ids:
            marker = await self._fetch_value(
                "SELECT EXISTS(SELECT 1 FROM t_share_requests "
                "WHERE tenant_id = $1 AND id = ANY($2::uuid[]) "
                "AND personal_data_involved = TRUE)",
                (tenant_id, list(request_ids)),
            )
            if marker:
                return True
        # Fallback: scan the JSON payloads for the personal-data marker.
        for row in rows:
            for column in ("before_state", "after_state", "metadata"):
                payload = row.get(column)
                if isinstance(payload, dict) and payload.get("personal_data_involved"):
                    return True
                if isinstance(payload, str) and "personal_data_involved\": true" in payload:
                    return True
        return False

    @staticmethod
    def _rows_to_csv(rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serialized = {}
            for col in _CSV_COLUMNS:
                value = row.get(col)
                if isinstance(value, (dict, list)):
                    serialized[col] = json.dumps(value, default=str)
                elif isinstance(value, (UUID, datetime)):
                    serialized[col] = value.isoformat() if isinstance(value, datetime) else str(value)
                else:
                    serialized[col] = value
            writer.writerow(serialized)
        return buf.getvalue()


def get_audit_export_service() -> AuditExportService:
    return AuditExportService()
