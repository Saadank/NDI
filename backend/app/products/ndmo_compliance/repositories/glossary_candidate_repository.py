"""GlossaryCandidateRepository — DB-extraction candidate terms.

All access to ndmo.t_glossary_db_candidates (BRD §6.4).  Candidates are mined
from source-DB column *metadata* only and reviewed before becoming draft terms.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)

_COLS = """
    id, tenant_id, connection_id, schema_name, table_name, column_name,
    inferred_name_en, ai_draft_definition, status, assigned_domain_id,
    assigned_to_user_id, dismiss_reason, promoted_term_id, created_at
"""


class GlossaryCandidateRepository(PostgresqlAsyncRepository):
    async def bulk_create(
        self, *, tenant_id: int, connection_id: UUID, rows: list[dict]
    ) -> list[dict]:
        """rows: [{schema_name, table_name, column_name, inferred_name_en}]."""
        created: list[dict] = []
        async with self._transaction() as conn:
            for r in rows:
                row = await self._fetch_row(
                    f"""
                    INSERT INTO ndmo.t_glossary_db_candidates
                        (tenant_id, connection_id, schema_name, table_name,
                         column_name, inferred_name_en, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                    RETURNING {_COLS}
                    """,
                    (tenant_id, connection_id, r["schema_name"], r["table_name"],
                     r["column_name"], r["inferred_name_en"]),
                    connection=conn,
                )
                created.append(row)
        return created

    async def list_candidates(
        self, *, tenant_id: int, status: str | None = "pending",
        schema: str | None = None, table: str | None = None,
        domain_id: UUID | None = None,
    ) -> list[dict]:
        conds = ["tenant_id = $1"]
        args: list = [tenant_id]

        def _p() -> str:
            return f"${len(args)}"

        if status:
            args.append(status)
            conds.append(f"status = {_p()}")
        if schema:
            args.append(schema)
            conds.append(f"schema_name = {_p()}")
        if table:
            args.append(table)
            conds.append(f"table_name = {_p()}")
        if domain_id:
            args.append(domain_id)
            conds.append(f"assigned_domain_id = {_p()}")
        return await self._fetch_all(
            f"SELECT {_COLS} FROM ndmo.t_glossary_db_candidates "
            f"WHERE {' AND '.join(conds)} ORDER BY schema_name, table_name, inferred_name_en",
            tuple(args),
        )

    async def find_by_id(self, *, candidate_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            f"SELECT {_COLS} FROM ndmo.t_glossary_db_candidates "
            f"WHERE id = $1 AND tenant_id = $2",
            (candidate_id, tenant_id),
        )

    async def set_ai_definition(
        self, *, candidate_id: UUID, tenant_id: int, definition: str
    ) -> None:
        await self._execute(
            "UPDATE ndmo.t_glossary_db_candidates SET ai_draft_definition = $3 "
            "WHERE id = $1 AND tenant_id = $2",
            (candidate_id, tenant_id, definition),
        )

    async def assign(
        self, *, candidate_id: UUID, tenant_id: int,
        domain_id: UUID | None, user_id: int | None,
    ) -> dict:
        return await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_db_candidates
            SET assigned_domain_id = COALESCE($3, assigned_domain_id),
                assigned_to_user_id = COALESCE($4, assigned_to_user_id)
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (candidate_id, tenant_id, domain_id, user_id),
        )

    async def mark_accepted(
        self, *, candidate_id: UUID, tenant_id: int, promoted_term_id: UUID,
        domain_id: UUID | None,
    ) -> None:
        await self._execute(
            """
            UPDATE ndmo.t_glossary_db_candidates
            SET status = 'accepted', promoted_term_id = $3,
                assigned_domain_id = COALESCE($4, assigned_domain_id)
            WHERE id = $1 AND tenant_id = $2
            """,
            (candidate_id, tenant_id, promoted_term_id, domain_id),
        )

    async def mark_dismissed(
        self, *, candidate_id: UUID, tenant_id: int, reason: str | None
    ) -> None:
        await self._execute(
            "UPDATE ndmo.t_glossary_db_candidates "
            "SET status = 'dismissed', dismiss_reason = $3 "
            "WHERE id = $1 AND tenant_id = $2",
            (candidate_id, tenant_id, reason),
        )

    async def dismiss_all_pending(
        self, *, tenant_id: int, table: str | None = None, reason: str | None = None
    ) -> int:
        """Bulk-dismiss every pending candidate (optionally just one table).
        Returns the number dismissed."""
        if table:
            result = await self._execute(
                "UPDATE ndmo.t_glossary_db_candidates "
                "SET status = 'dismissed', dismiss_reason = $3 "
                "WHERE tenant_id = $1 AND status = 'pending' AND table_name = $2",
                (tenant_id, table, reason),
            )
        else:
            result = await self._execute(
                "UPDATE ndmo.t_glossary_db_candidates "
                "SET status = 'dismissed', dismiss_reason = $2 "
                "WHERE tenant_id = $1 AND status = 'pending'",
                (tenant_id, reason),
            )
        return int(result.split()[-1]) if result else 0

    async def list_pending_undrafted(
        self, *, tenant_id: int, limit: int = 1000
    ) -> list[dict]:
        """Pending candidates that still lack an AI definition (drives the
        resumable drafting job — re-query each run so it picks up where an
        interrupted run left off)."""
        return await self._fetch_all(
            f"""
            SELECT {_COLS} FROM ndmo.t_glossary_db_candidates
            WHERE tenant_id = $1 AND status = 'pending'
              AND ai_draft_definition IS NULL
            ORDER BY schema_name, table_name, inferred_name_en
            LIMIT $2
            """,
            (tenant_id, limit),
        )

    async def draft_counts(self, *, tenant_id: int) -> dict:
        """(total pending, of which drafted) for progress reporting."""
        row = await self._fetch_row_optional(
            """
            SELECT COUNT(*) AS total,
                   COUNT(ai_draft_definition) AS drafted
            FROM ndmo.t_glossary_db_candidates
            WHERE tenant_id = $1 AND status = 'pending'
            """,
            (tenant_id,),
        )
        return {"total": int(row["total"]), "drafted": int(row["drafted"])} if row else {"total": 0, "drafted": 0}

    async def list_schemas_tables(self, *, tenant_id: int) -> list[dict]:
        """Distinct schema/table pairs in the pending queue, for filters."""
        return await self._fetch_all(
            "SELECT DISTINCT schema_name, table_name FROM ndmo.t_glossary_db_candidates "
            "WHERE tenant_id = $1 AND status = 'pending' ORDER BY schema_name, table_name",
            (tenant_id,),
        )
