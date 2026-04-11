import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)


class GlossaryService(PostgresqlAsyncRepository):

    async def list_entries(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_glossary_entries WHERE tenant_id = $1 ORDER BY term", (tenant_id,)
        )

    async def create_entry(self, tenant_id: int, term: str, definition: str | None,
                           category: str | None, connection_id: UUID | None, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_glossary_entries (tenant_id, term, definition, category, connection_id, created_by)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            (tenant_id, term, definition, category, connection_id, created_by),
        )

    async def update_entry(self, entry_id: UUID, tenant_id: int, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        args.extend([entry_id, tenant_id])
        return await self._fetch_row(
            f"UPDATE t_glossary_entries SET {', '.join(set_clauses)} WHERE id = ${idx} AND tenant_id = ${idx + 1} RETURNING *",
            tuple(args),
        )

    async def delete_entry(self, entry_id: UUID, tenant_id: int) -> str:
        return await self._execute(
            "DELETE FROM t_glossary_entries WHERE id = $1 AND tenant_id = $2", (entry_id, tenant_id)
        )


def get_glossary_service() -> GlossaryService:
    return GlossaryService()
