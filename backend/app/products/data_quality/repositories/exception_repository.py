"""Persistence for dq.t_dq_exceptions — Step 5.

Three lifecycle states (`active`, `revoked`, `expired`) with read-time
expiry: callers should treat any row where `status='active' AND expires_at <
now()` as effectively expired. The Step 8 sweeper will eventually flip those
to `status='expired'` for cleanliness, but until then nothing in the read
path relies on the column being authoritative.
"""
from datetime import datetime

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ExceptionRepository(PostgresqlAsyncRepository):

    async def revoke_active_for_rule(
        self, *, tenant_id: int, active_rule_id: int,
        user_id: int | None, reason: str | None,
    ) -> None:
        """Mark any currently-active exception on a rule as revoked. Used by
        `insert_active` so the partial unique index doesn't trip when the user
        replaces an exception (e.g. extends the ceiling)."""
        await self._execute(
            """UPDATE dq.t_dq_exceptions
                  SET status = 'revoked',
                      revoked_at = CURRENT_TIMESTAMP,
                      revoked_by = $3,
                      revoke_reason = COALESCE($4, 'Replaced by new exception')
                WHERE tenant_id = $1
                  AND active_rule_id = $2
                  AND status = 'active'""",
            (tenant_id, active_rule_id, user_id, reason),
        )

    async def insert_active(
        self, *, tenant_id: int, profile_id: int, active_rule_id: int,
        reason_category: str, explanation: str,
        violation_count_ceiling: int | None,
        expires_at: datetime, created_by: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_exceptions
                  (tenant_id, profile_id, active_rule_id,
                   reason_category, explanation, violation_count_ceiling,
                   status, expires_at, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, 'active', $7, $8)
               RETURNING *""",
            (tenant_id, profile_id, active_rule_id,
             reason_category, explanation, violation_count_ceiling,
             expires_at, created_by),
        )

    async def find_by_id(self, exception_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_exceptions
                WHERE id = $1 AND tenant_id = $2""",
            (exception_id, tenant_id),
        )

    async def list_for_profile(
        self, *, tenant_id: int, profile_id: int,
        include_revoked: bool = False,
    ) -> list[dict]:
        """Active + currently-effective exceptions, ordered by expiry. With
        include_revoked=true, also returns terminal rows (audit trail)."""
        where = "e.tenant_id = $1 AND e.profile_id = $2"
        if not include_revoked:
            where += " AND e.status = 'active'"
        return await self._fetch_all(
            f"""SELECT e.*,
                       ar.column_name,
                       c.dimension     AS c_dimension,
                       c.concept       AS c_concept,
                       c.rule_type     AS c_rule_type,
                       c.severity      AS c_severity,
                       (e.status = 'active' AND e.expires_at < CURRENT_TIMESTAMP)
                            AS is_past_expiry
                  FROM dq.t_dq_exceptions e
                  JOIN dq.t_dq_active_rules ar ON ar.id = e.active_rule_id
                  JOIN dq.t_dq_concepts     c  ON c.id = ar.concept_id
                 WHERE {where}
              ORDER BY e.status,
                       (e.status = 'active' AND e.expires_at < CURRENT_TIMESTAMP) DESC,
                       e.expires_at ASC""",
            (tenant_id, profile_id),
        )

    async def find_active_for_rules(
        self, *, tenant_id: int, active_rule_ids: list[int],
    ) -> dict[int, dict]:
        """Bulk lookup keyed by active_rule_id. Returns only effectively-active
        rows: status='active' AND expires_at > now(). Used by ScoringService
        when computing governed_score for a scan."""
        if not active_rule_ids:
            return {}
        rows = await self._fetch_all(
            """SELECT * FROM dq.t_dq_exceptions
                WHERE tenant_id = $1
                  AND active_rule_id = ANY($2::int[])
                  AND status = 'active'
                  AND expires_at > CURRENT_TIMESTAMP""",
            (tenant_id, active_rule_ids),
        )
        return {r["active_rule_id"]: r for r in rows}

    async def find_active_for_scan(
        self, *, tenant_id: int, scan_id: int,
    ) -> dict[int, dict]:
        """Same as find_active_for_rules but resolves the rule set from the
        issues already persisted for the scan — saves the caller a join."""
        rows = await self._fetch_all(
            """SELECT e.* FROM dq.t_dq_exceptions e
                JOIN (
                    SELECT DISTINCT active_rule_id
                      FROM dq.t_dq_issues
                     WHERE tenant_id = $1 AND scan_id = $2
                ) ir ON ir.active_rule_id = e.active_rule_id
               WHERE e.tenant_id = $1
                 AND e.status = 'active'
                 AND e.expires_at > CURRENT_TIMESTAMP""",
            (tenant_id, scan_id),
        )
        return {r["active_rule_id"]: r for r in rows}

    async def revoke(
        self, exception_id: int, tenant_id: int, *,
        user_id: int | None, reason: str | None,
    ) -> dict:
        return await self._fetch_row(
            """UPDATE dq.t_dq_exceptions
                  SET status = 'revoked',
                      revoked_at = CURRENT_TIMESTAMP,
                      revoked_by = $3,
                      revoke_reason = $4
                WHERE id = $1 AND tenant_id = $2 AND status = 'active'
            RETURNING *""",
            (exception_id, tenant_id, user_id, (reason or "").strip() or None),
        )

    async def update_expiry(
        self, exception_id: int, tenant_id: int, *,
        new_expires_at: datetime,
    ) -> dict:
        return await self._fetch_row(
            """UPDATE dq.t_dq_exceptions
                  SET expires_at = $3
                WHERE id = $1 AND tenant_id = $2 AND status = 'active'
            RETURNING *""",
            (exception_id, tenant_id, new_expires_at),
        )
