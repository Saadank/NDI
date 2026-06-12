"""GlossaryReviewRepository — append-only review history.

ndmo.t_glossary_term_reviews rows are immutable for audit (BRD §5.2).
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


class GlossaryReviewRepository(PostgresqlAsyncRepository):
    async def add(
        self, *, tenant_id: int, term_id: UUID, reviewer_id: int,
        decision: str, version: int | None = None, note: str | None = None,
    ) -> UUID:
        return await self._fetch_value(
            """
            INSERT INTO ndmo.t_glossary_term_reviews
                (tenant_id, term_id, version, reviewer_id, decision, note)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            (tenant_id, term_id, version, reviewer_id, decision, note),
        )

    async def list_for_term(self, *, term_id: UUID, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """
            SELECT id, version, reviewer_id, decision, note, reviewed_at
            FROM ndmo.t_glossary_term_reviews
            WHERE term_id = $1 AND tenant_id = $2
            ORDER BY reviewed_at DESC
            """,
            (term_id, tenant_id),
        )
