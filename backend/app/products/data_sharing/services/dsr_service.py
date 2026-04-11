import logging
from datetime import timedelta
from uuid import UUID

from app.platform.services.audit_service import AuditService
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.structures.auth_user import AuthUser
from app.utils.timezone import now

logger = logging.getLogger(__name__)

DSR_RESPONSE_DAYS = 30


class DsrService(PostgresqlAsyncRepository):

    def __init__(self) -> None:
        self.audit = AuditService()

    async def create_dsr(self, data: dict, auth_user: AuthUser) -> dict:
        deadline = now() + timedelta(days=DSR_RESPONSE_DAYS)
        dsr = await self._fetch_row(
            """INSERT INTO t_dsr_requests
               (tenant_id, subject_name, subject_email, subject_id_type, subject_id_value,
                request_type, description, response_deadline, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING *""",
            (auth_user.tenant_id, data["subject_name"], data.get("subject_email"),
             data.get("subject_id_type"), data.get("subject_id_value"),
             data["request_type"], data.get("description"), deadline, auth_user.user_id),
        )

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="dsr.created",
            resource_type="dsr_request", resource_id=str(dsr["id"]),
            actor_id=auth_user.user_id,
        )
        return dsr

    async def get_dsr(self, dsr_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            "SELECT * FROM t_dsr_requests WHERE id = $1 AND tenant_id = $2", (dsr_id, tenant_id)
        )

    async def list_dsrs(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_dsr_requests WHERE tenant_id = $1 ORDER BY created_at DESC", (tenant_id,)
        )

    async def respond_to_dsr(self, dsr_id: UUID, response_summary: str, auth_user: AuthUser) -> dict:
        return await self._fetch_row(
            """UPDATE t_dsr_requests SET status = 'responded', responded_at = CURRENT_TIMESTAMP,
               response_summary = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *""",
            (response_summary, dsr_id),
        )


def get_dsr_service() -> DsrService:
    return DsrService()
