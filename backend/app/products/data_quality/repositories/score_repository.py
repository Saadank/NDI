"""Persistence for dq.t_dq_score_history + dq.t_dq_score_thresholds.

Step 4 of IDQP. Score rows are immutable per (scan, dimension) — ON CONFLICT
DO NOTHING so the validator can be retried without dup-rowing the history.
Thresholds are mutable per tenant; the service caches snapshots on score rows
so historical tiers stay stable when an admin retunes the thresholds later.
"""
import json

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ScoreRepository(PostgresqlAsyncRepository):

    # ---------- score_history --------------------------------------------

    async def insert_score(
        self, *, tenant_id: int, profile_id: int, scan_id: int,
        scope_type: str = "profile", scope_key: str = "",
        dimension: str, pass_rate: float,
        rule_count: int, pass_count: int, fail_count: int, error_count: int,
        raw_score: float, governed_score: float, tier: str,
        thresholds_snapshot: dict | None,
        weighted_score: float | None = None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_score_history
                  (tenant_id, profile_id, scan_id,
                   scope_type, scope_key, dimension,
                   pass_rate, rule_count, pass_count, fail_count, error_count,
                   raw_score, governed_score, tier,
                   thresholds_snapshot, weighted_score)
               VALUES ($1, $2, $3,
                       $4, $5, $6,
                       $7, $8, $9, $10, $11,
                       $12, $13, $14,
                       $15::jsonb, $16)
               ON CONFLICT (scan_id, scope_type, scope_key, dimension) DO UPDATE SET
                   pass_rate           = EXCLUDED.pass_rate,
                   rule_count          = EXCLUDED.rule_count,
                   pass_count          = EXCLUDED.pass_count,
                   fail_count          = EXCLUDED.fail_count,
                   error_count         = EXCLUDED.error_count,
                   raw_score           = EXCLUDED.raw_score,
                   governed_score      = EXCLUDED.governed_score,
                   tier                = EXCLUDED.tier,
                   thresholds_snapshot = EXCLUDED.thresholds_snapshot,
                   weighted_score      = EXCLUDED.weighted_score,
                   computed_at         = CURRENT_TIMESTAMP
               RETURNING *""",
            (tenant_id, profile_id, scan_id,
             scope_type, scope_key, dimension,
             pass_rate, rule_count, pass_count, fail_count, error_count,
             raw_score, governed_score, tier,
             json.dumps(thresholds_snapshot or {}),
             weighted_score),
        )

    async def latest_for_profile(
        self, *, tenant_id: int, profile_id: int,
    ) -> list[dict]:
        """Score rows + previous-scan deltas for the most recent successful
        scan of the profile. One row per dimension (incl. 'overall').

        Uses LAG() over the full history so the trend arrow points at the
        delta from the last comparable scan."""
        return await self._fetch_all(
            """WITH ranked AS (
                  SELECT sh.*,
                         LAG(sh.pass_rate) OVER (
                             PARTITION BY sh.profile_id, sh.dimension
                             ORDER BY sh.scan_id
                         ) AS prev_pass_rate,
                         ROW_NUMBER() OVER (
                             PARTITION BY sh.profile_id, sh.dimension
                             ORDER BY sh.scan_id DESC
                         ) AS rn
                    FROM dq.t_dq_score_history sh
                   WHERE sh.tenant_id = $1
                     AND sh.profile_id = $2
                     AND sh.scope_type = 'profile'
               )
               SELECT * FROM ranked WHERE rn = 1
            ORDER BY CASE dimension
                       WHEN 'overall' THEN 0
                       WHEN 'completeness' THEN 1
                       WHEN 'validity' THEN 2
                       WHEN 'uniqueness' THEN 3
                       ELSE 9
                     END""",
            (tenant_id, profile_id),
        )

    async def trend_for_profile(
        self, *, tenant_id: int, profile_id: int, limit: int = 50,
    ) -> list[dict]:
        """Score history per (scan, dimension) for trend charts. Newest first."""
        return await self._fetch_all(
            """SELECT sh.*, s.finished_at
                 FROM dq.t_dq_score_history sh
                 JOIN dq.t_dq_scans s ON s.id = sh.scan_id
                WHERE sh.tenant_id = $1 AND sh.profile_id = $2
                  AND sh.scope_type = 'profile'
             ORDER BY sh.scan_id DESC, sh.dimension
                LIMIT $3""",
            (tenant_id, profile_id, limit),
        )

    async def rule_occurrences_for_scan(
        self, *, tenant_id: int, scan_id: int,
    ) -> list[dict]:
        """Per-rule pass-rate breakdown for the rule-occurrences table on
        the Metrics tab. Mirrors Informatica's Results table columns."""
        return await self._fetch_all(
            """SELECT i.id              AS issue_id,
                      i.column_name,
                      i.dimension,
                      i.rule_type,
                      i.severity,
                      i.row_count,
                      i.violation_count,
                      i.violation_rate,
                      i.status,
                      i.diagnostic_text,
                      i.created_at,
                      c.concept,
                      c.notes           AS concept_description,
                      (1 - COALESCE(i.violation_rate, 0))::numeric(6,5) AS pass_rate
                 FROM dq.t_dq_issues i
                 JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                WHERE i.tenant_id = $1 AND i.scan_id = $2
             ORDER BY i.dimension, i.column_name, c.concept""",
            (tenant_id, scan_id),
        )

    # ---------- score_thresholds -----------------------------------------

    async def get_thresholds_for_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT * FROM dq.t_dq_score_thresholds
                WHERE tenant_id = $1
             ORDER BY dimension""",
            (tenant_id,),
        )

    async def upsert_thresholds(
        self, *, tenant_id: int, dimension: str,
        good_min: float, acceptable_min: float,
        severity_weighting_enabled: bool,
        updated_by: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_score_thresholds
                  (tenant_id, dimension, good_min, acceptable_min,
                   severity_weighting_enabled, updated_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (tenant_id, dimension) DO UPDATE SET
                   good_min                   = EXCLUDED.good_min,
                   acceptable_min             = EXCLUDED.acceptable_min,
                   severity_weighting_enabled = EXCLUDED.severity_weighting_enabled,
                   updated_by                 = EXCLUDED.updated_by,
                   updated_at                 = CURRENT_TIMESTAMP
               RETURNING *""",
            (tenant_id, dimension, good_min, acceptable_min,
             severity_weighting_enabled, updated_by),
        )
