"""Persistence for dq.t_dq_llm_calls — audit trail.

Records token counts, latency, status, and content hashes for every LLM
round-trip. Never stores the raw prompt or response — hashes only — so
the audit table can't accidentally retain PII from a column-rich Excel
file or a prompt fragment that slipped past the anonymizer.
"""
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class LlmCallRepository(PostgresqlAsyncRepository):

    async def insert(
        self, *, tenant_id: int, purpose: str, model: str, prompt_version: int,
        input_tokens: int | None, output_tokens: int | None,
        cache_read_tokens: int | None, cache_creation_tokens: int | None,
        latency_ms: int | None, status: str, error: str | None,
        prompt_hash: str | None, response_hash: str | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_llm_calls
                  (tenant_id, purpose, model, prompt_version,
                   input_tokens, output_tokens,
                   cache_read_tokens, cache_creation_tokens,
                   latency_ms, status, error,
                   prompt_hash, response_hash)
               VALUES ($1, $2, $3, $4,
                       $5, $6,
                       $7, $8,
                       $9, $10, $11,
                       $12, $13)
               RETURNING *""",
            (tenant_id, purpose, model, prompt_version,
             input_tokens, output_tokens,
             cache_read_tokens, cache_creation_tokens,
             latency_ms, status, error,
             prompt_hash, response_hash),
        )

    async def list_recent(
        self, tenant_id: int, *, limit: int = 100,
        purpose: str | None = None, status: str | None = None,
    ) -> list[dict]:
        sql = ["SELECT * FROM dq.t_dq_llm_calls WHERE tenant_id = $1"]
        args: list = [tenant_id]
        if purpose:
            args.append(purpose); sql.append(f"AND purpose = ${len(args)}")
        if status:
            args.append(status); sql.append(f"AND status = ${len(args)}")
        args.append(limit)
        sql.append(f"ORDER BY created_at DESC LIMIT ${len(args)}")
        return await self._fetch_all(" ".join(sql), tuple(args))

    async def aggregate_for_tenant(
        self, tenant_id: int, *, since_days: int = 30,
    ) -> list[dict]:
        """For a cost-overview dashboard: per-purpose totals + p95 latency
        over the last N days. (Used by 6.7's import-detail screen.)"""
        return await self._fetch_all(
            """SELECT purpose,
                      COUNT(*)                              AS calls,
                      COUNT(*) FILTER (WHERE status='ok')   AS successes,
                      SUM(COALESCE(input_tokens,0))         AS input_tokens,
                      SUM(COALESCE(output_tokens,0))        AS output_tokens,
                      PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
                 FROM dq.t_dq_llm_calls
                WHERE tenant_id = $1
                  AND created_at >= NOW() - ($2::int * INTERVAL '1 day')
             GROUP BY purpose
             ORDER BY purpose""",
            (tenant_id, since_days),
        )
