"""Persistence for dq.t_dq_active_rules — materialized matcher decisions."""
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ActiveRuleRepository(PostgresqlAsyncRepository):

    async def list_for_profile(
        self, *, tenant_id: int, profile_id: int,
    ) -> list[dict]:
        return await self._fetch_all(
            """SELECT ar.*,
                      c.dimension     AS c_dimension,
                      c.concept       AS c_concept,
                      c.rule_type     AS c_rule_type,
                      c.severity      AS c_severity,
                      c.parameter     AS c_parameter
                 FROM dq.t_dq_active_rules ar
                 JOIN dq.t_dq_concepts c ON c.id = ar.concept_id
                WHERE ar.tenant_id = $1 AND ar.profile_id = $2
             ORDER BY ar.column_name, c.dimension, c.concept""",
            (tenant_id, profile_id),
        )

    async def list_active_for_validator_by_profile(
        self, *, tenant_id: int, profile_id: int,
    ) -> list[dict]:
        return await self._fetch_all(
            """SELECT ar.id AS active_rule_id,
                      ar.column_name, ar.concept_id, ar.confidence,
                      c.dimension, c.concept, c.rule_type, c.parameter, c.severity
                 FROM dq.t_dq_active_rules ar
                 JOIN dq.t_dq_concepts c ON c.id = ar.concept_id
                WHERE ar.tenant_id = $1 AND ar.profile_id = $2
                  AND ar.approval_status IN ('auto_applied','approved')
                  AND c.enabled = TRUE
             ORDER BY ar.column_name, c.dimension""",
            (tenant_id, profile_id),
        )

    async def delete_stale_proposals_by_profile(
        self, *, tenant_id: int, profile_id: int, keep_concept_ids: list[int],
    ) -> str:
        return await self._execute(
            """DELETE FROM dq.t_dq_active_rules
                WHERE tenant_id = $1 AND profile_id = $2
                  AND approval_status IN ('auto_applied','proposed')
                  AND NOT (concept_id = ANY($3::int[]))""",
            (tenant_id, profile_id, keep_concept_ids),
        )

    async def list_for_table(
        self, *, tenant_id: int, connection_id: UUID,
        schema_name: str, table_name: str,
    ) -> list[dict]:
        return await self._fetch_all(
            """SELECT ar.*,
                      c.dimension     AS c_dimension,
                      c.concept       AS c_concept,
                      c.rule_type     AS c_rule_type,
                      c.severity      AS c_severity,
                      c.parameter     AS c_parameter
                 FROM dq.t_dq_active_rules ar
                 JOIN dq.t_dq_concepts c ON c.id = ar.concept_id
                WHERE ar.tenant_id = $1
                  AND ar.connection_id = $2
                  AND ar.schema_name = $3
                  AND ar.table_name = $4
             ORDER BY ar.column_name, c.dimension, c.concept""",
            (tenant_id, connection_id, schema_name, table_name),
        )

    async def find_by_id(self, rule_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_active_rules
                WHERE id = $1 AND tenant_id = $2""",
            (rule_id, tenant_id),
        )

    async def upsert(
        self, *, tenant_id: int, profile_id: int, connection_id: UUID,
        schema_name: str, table_name: str, column_name: str, concept_id: int,
        matched_by: str, confidence: str, matcher_score: float | None,
        matcher_reasoning: str | None, approval_status: str,
    ) -> dict:
        """Insert or refresh a matcher decision. ON CONFLICT preserves
        approved/blocked status (set by humans) — only matcher metadata
        and proposed/auto_applied entries are overwritten."""
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_active_rules
                  (tenant_id, profile_id, connection_id, schema_name, table_name,
                   column_name, concept_id, matched_by, confidence,
                   matcher_score, matcher_reasoning, approval_status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
               ON CONFLICT (connection_id, schema_name, table_name, column_name, concept_id)
               DO UPDATE SET
                   profile_id        = EXCLUDED.profile_id,
                   matched_by        = EXCLUDED.matched_by,
                   confidence        = EXCLUDED.confidence,
                   matcher_score     = EXCLUDED.matcher_score,
                   matcher_reasoning = EXCLUDED.matcher_reasoning,
                   -- Preserve human decisions; only refresh auto/proposed rows.
                   approval_status   = CASE
                       WHEN dq.t_dq_active_rules.approval_status IN ('approved','blocked')
                            THEN dq.t_dq_active_rules.approval_status
                       ELSE EXCLUDED.approval_status
                   END,
                   updated_at = CURRENT_TIMESTAMP
               RETURNING *""",
            (tenant_id, profile_id, connection_id, schema_name, table_name,
             column_name, concept_id, matched_by, confidence,
             matcher_score, matcher_reasoning, approval_status),
        )

    async def update_approval(
        self, rule_id: int, tenant_id: int, *,
        approval_status: str, approved_by: int | None,
        blocked_reason: str | None,
    ) -> dict:
        # $3 is referenced both in `SET approval_status = ...` (varchar) and
        # in a `CASE WHEN $3 IN (...)` (text). Cast once at the binding site
        # so asyncpg picks a single type.
        return await self._fetch_row(
            """UPDATE dq.t_dq_active_rules
                  SET approval_status = $3::varchar,
                      approved_by     = $4,
                      approved_at     = CASE WHEN $3::varchar IN ('approved','auto_applied')
                                             THEN CURRENT_TIMESTAMP ELSE approved_at END,
                      blocked_reason  = $5,
                      updated_at      = CURRENT_TIMESTAMP
                WHERE id = $1 AND tenant_id = $2
            RETURNING *""",
            (rule_id, tenant_id, approval_status, approved_by, blocked_reason),
        )

    async def delete_by_id(self, rule_id: int, tenant_id: int) -> str:
        """Hard-delete a single active_rule. Caller MUST first verify
        there are no t_dq_issues referencing it — the FK is ON DELETE
        CASCADE, which would silently destroy validator output."""
        return await self._execute(
            """DELETE FROM dq.t_dq_active_rules
                WHERE id = $1 AND tenant_id = $2""",
            (rule_id, tenant_id),
        )

    async def delete_stale_proposals(
        self, *, tenant_id: int, connection_id: UUID, schema_name: str,
        table_name: str, keep_concept_ids: list[int],
    ) -> str:
        """Drop matcher proposals (auto_applied/proposed) for this table whose
        concept is no longer in the matcher's output. Approved/blocked rows
        survive — those represent human commitments, not just matcher state."""
        return await self._execute(
            """DELETE FROM dq.t_dq_active_rules
                WHERE tenant_id = $1
                  AND connection_id = $2
                  AND schema_name = $3
                  AND table_name = $4
                  AND approval_status IN ('auto_applied','proposed')
                  AND NOT (concept_id = ANY($5::int[]))""",
            (tenant_id, connection_id, schema_name, table_name, keep_concept_ids),
        )

    async def list_active_for_validator(
        self, *, tenant_id: int, connection_id: UUID,
        schema_name: str, table_name: str,
    ) -> list[dict]:
        """Rules the validator should run: auto_applied + approved (NOT proposed
        and NOT blocked). Used by Step 3c."""
        return await self._fetch_all(
            """SELECT ar.id AS active_rule_id,
                      ar.column_name, ar.concept_id, ar.confidence,
                      c.dimension, c.concept, c.rule_type, c.parameter, c.severity
                 FROM dq.t_dq_active_rules ar
                 JOIN dq.t_dq_concepts c ON c.id = ar.concept_id
                WHERE ar.tenant_id = $1
                  AND ar.connection_id = $2
                  AND ar.schema_name = $3
                  AND ar.table_name = $4
                  AND ar.approval_status IN ('auto_applied','approved')
                  AND c.enabled = TRUE
             ORDER BY ar.column_name, c.dimension""",
            (tenant_id, connection_id, schema_name, table_name),
        )
