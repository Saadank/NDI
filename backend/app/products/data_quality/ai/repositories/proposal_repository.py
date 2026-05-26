"""Persistence for dq.t_dq_proposals — the human-review queue.

Per-row LLM proposals flow through these statuses:
    pending -> approved | rejected | rejected_by_validator | unsupported_logic
    approved -> rolled_back  (when the import is rolled back)

The applier (Step 6.7+) writes ``applied_target_id`` / ``applied_target_kind``
after the deterministic target is created so rollback can walk backward.
"""
import json

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ProposalRepository(PostgresqlAsyncRepository):

    async def insert(
        self, *, tenant_id: int, import_id: int | None, source_row: int | None,
        kind: str, status: str, confidence: str | None,
        payload: dict, candidates: list | None,
        proposed_value: dict | None, reasoning: str | None,
        error_reason: str | None,
        target_concept_id: int | None,
        llm_call_id: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_proposals
                  (tenant_id, import_id, source_row,
                   kind, status, confidence,
                   payload, candidates, proposed_value,
                   reasoning, error_reason,
                   target_concept_id, llm_call_id)
               VALUES ($1, $2, $3,
                       $4, $5, $6,
                       $7::jsonb, $8::jsonb, $9::jsonb,
                       $10, $11,
                       $12, $13)
               RETURNING *""",
            (tenant_id, import_id, source_row,
             kind, status, confidence,
             json.dumps(payload),
             json.dumps(candidates) if candidates is not None else None,
             json.dumps(proposed_value) if proposed_value is not None else None,
             reasoning, error_reason,
             target_concept_id, llm_call_id),
        )

    async def find_by_id(self, proposal_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_proposals
                WHERE id = $1 AND tenant_id = $2""",
            (proposal_id, tenant_id),
        )

    async def list_for_import(
        self, import_id: int, tenant_id: int, *,
        status: str | None = None, confidence: str | None = None,
    ) -> list[dict]:
        sql = [
            "SELECT * FROM dq.t_dq_proposals "
            "WHERE import_id = $1 AND tenant_id = $2"
        ]
        args: list = [import_id, tenant_id]
        if status:
            args.append(status); sql.append(f"AND status = ${len(args)}")
        if confidence:
            args.append(confidence); sql.append(f"AND confidence = ${len(args)}")
        sql.append("ORDER BY source_row NULLS LAST, id")
        return await self._fetch_all(" ".join(sql), tuple(args))

    async def list_for_tenant(
        self, tenant_id: int, *,
        status: str | None = None, limit: int = 200,
    ) -> list[dict]:
        sql = ["SELECT * FROM dq.t_dq_proposals WHERE tenant_id = $1"]
        args: list = [tenant_id]
        if status:
            args.append(status); sql.append(f"AND status = ${len(args)}")
        args.append(limit)
        sql.append(f"ORDER BY created_at DESC LIMIT ${len(args)}")
        return await self._fetch_all(" ".join(sql), tuple(args))

    async def mark_reviewed(
        self, proposal_id: int, tenant_id: int, *,
        status: str, final_value: dict | None, reviewer_id: int,
        applied_target_id: int | None = None,
        applied_target_kind: str | None = None,
    ) -> dict:
        return await self._fetch_row(
            """UPDATE dq.t_dq_proposals
                  SET status              = $3,
                      final_value         = COALESCE($4::jsonb, final_value),
                      reviewer_id         = $5,
                      reviewed_at         = NOW(),
                      applied_target_id   = COALESCE($6, applied_target_id),
                      applied_target_kind = COALESCE($7, applied_target_kind)
                WHERE id = $1 AND tenant_id = $2
                RETURNING *""",
            (proposal_id, tenant_id, status,
             json.dumps(final_value) if final_value is not None else None,
             reviewer_id, applied_target_id, applied_target_kind),
        )

    async def mark_rolled_back(self, import_id: int, tenant_id: int) -> None:
        """Bulk-mark every applied proposal in an import as rolled_back."""
        await self._execute(
            """UPDATE dq.t_dq_proposals
                  SET status = 'rolled_back'
                WHERE import_id = $1 AND tenant_id = $2
                  AND status = 'approved'""",
            (import_id, tenant_id),
        )
