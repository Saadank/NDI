"""Persistence for dq.t_dq_glossary_terms — business glossary rows
(BRD Table 11). Read by column_match to enrich prompts with the tenant's
local terminology."""
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class GlossaryRepository(PostgresqlAsyncRepository):

    async def insert_batch(
        self, *, tenant_id: int, import_id: int, rows: list[dict],
    ) -> int:
        """Bulk-insert a parsed glossary spreadsheet. Each ``rows`` element
        is ``{term, definition, synonyms[], language}``. Returns the count."""
        if not rows:
            return 0
        inserted = 0
        for r in rows:
            await self._execute(
                """INSERT INTO dq.t_dq_glossary_terms
                      (tenant_id, import_id, term, definition, synonyms, language)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                (tenant_id, import_id, r["term"], r.get("definition"),
                 r.get("synonyms") or [], r.get("language")),
            )
            inserted += 1
        return inserted

    async def list_for_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT * FROM dq.t_dq_glossary_terms
                WHERE tenant_id = $1
             ORDER BY term""",
            (tenant_id,),
        )

    async def list_for_import(self, import_id: int, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT * FROM dq.t_dq_glossary_terms
                WHERE import_id = $1 AND tenant_id = $2
             ORDER BY id""",
            (import_id, tenant_id),
        )

    async def delete_for_import(self, import_id: int, tenant_id: int) -> None:
        """Used during rollback."""
        await self._execute(
            """DELETE FROM dq.t_dq_glossary_terms
                WHERE import_id = $1 AND tenant_id = $2""",
            (import_id, tenant_id),
        )
