"""GlossaryLlmRepository — audit log of AI-assist calls.

Writes ndmo.t_glossary_llm_calls.  Per BRD §6.3 / FR-023 + NFR-4 we store
content **hashes only** (never the prompt or completion text), plus token
count, latency, and a success flag.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


class GlossaryLlmRepository(PostgresqlAsyncRepository):
    async def record(
        self, *, tenant_id: int, purpose: str, input_hash: str | None,
        output_hash: str | None, tokens_used: int | None,
        latency_ms: int | None, success: bool, term_id: UUID | None = None,
    ) -> None:
        await self._execute(
            """
            INSERT INTO ndmo.t_glossary_llm_calls
                (tenant_id, term_id, purpose, input_hash, output_hash,
                 tokens_used, latency_ms, success)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            (tenant_id, term_id, purpose, input_hash, output_hash,
             tokens_used, latency_ms, success),
        )
