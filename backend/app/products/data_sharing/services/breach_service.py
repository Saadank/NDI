import logging
from datetime import timedelta
from uuid import UUID

from app.platform.services.audit_service import AuditService
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.structures.auth_user import AuthUser
from app.utils.timezone import now

logger = logging.getLogger(__name__)

SDAIA_NOTIFICATION_HOURS = 72


class BreachService(PostgresqlAsyncRepository):

    def __init__(self) -> None:
        self.audit = AuditService()

    async def report_breach(self, data: dict, auth_user: AuthUser) -> dict:
        deadline = now() + timedelta(hours=SDAIA_NOTIFICATION_HOURS)
        breach = await self._fetch_row(
            """INSERT INTO t_breach_events
               (tenant_id, request_id, title, description, severity, reported_by, sdaia_notification_deadline)
               VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *""",
            (auth_user.tenant_id, data.get("request_id"), data["title"], data["description"],
             data.get("severity", "medium"), auth_user.user_id, deadline),
        )

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="breach.reported",
            resource_type="breach_event", resource_id=str(breach["id"]),
            actor_id=auth_user.user_id, request_id=data.get("request_id"),
        )
        return breach

    async def get_breach(self, breach_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            "SELECT * FROM t_breach_events WHERE id = $1 AND tenant_id = $2", (breach_id, tenant_id)
        )

    async def list_breaches(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_breach_events WHERE tenant_id = $1 ORDER BY created_at DESC", (tenant_id,)
        )

    async def mark_sdaia_notified(self, breach_id: UUID, auth_user: AuthUser) -> dict:
        return await self._fetch_row(
            "UPDATE t_breach_events SET sdaia_notified_at = CURRENT_TIMESTAMP, status = 'notified' WHERE id = $1 RETURNING *",
            (breach_id,),
        )


def get_breach_service() -> BreachService:
    return BreachService()
