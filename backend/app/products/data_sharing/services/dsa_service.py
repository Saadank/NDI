import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class DsaService(PostgresqlAsyncRepository):

    async def create_dsa(self, data: dict, auth_user: AuthUser) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_data_sharing_agreements
               (tenant_id, request_id, counterparty_tenant_id, title, conditions, created_by)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            (auth_user.tenant_id, data.get("request_id"), data.get("counterparty_tenant_id"),
             data["title"], data.get("conditions"), auth_user.user_id),
        )

    async def get_dsa(self, dsa_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            "SELECT * FROM t_data_sharing_agreements WHERE id = $1 AND tenant_id = $2", (dsa_id, tenant_id)
        )

    async def list_dsas(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_data_sharing_agreements WHERE tenant_id = $1 ORDER BY created_at DESC", (tenant_id,)
        )

    async def accept_dsa(self, dsa_id: UUID, side: str, auth_user: AuthUser) -> dict:
        if side == "source":
            return await self._fetch_row(
                "UPDATE t_data_sharing_agreements SET accepted_by_source = TRUE, accepted_by_source_at = CURRENT_TIMESTAMP, accepted_by_source_user = $1 WHERE id = $2 RETURNING *",
                (auth_user.user_id, dsa_id),
            )
        return await self._fetch_row(
            "UPDATE t_data_sharing_agreements SET accepted_by_receiver = TRUE, accepted_by_receiver_at = CURRENT_TIMESTAMP, accepted_by_receiver_user = $1 WHERE id = $2 RETURNING *",
            (auth_user.user_id, dsa_id),
        )


def get_dsa_service() -> DsaService:
    return DsaService()
