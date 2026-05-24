"""Persistence for dq.t_dq_issues — validator findings per (scan, rule)."""
import json
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class IssueRepository(PostgresqlAsyncRepository):

    async def insert(self, *, tenant_id: int, scan_id: int, profile_id: int,
                     connection_id: UUID, schema_name: str, table_name: str,
                     column_name: str, active_rule_id: int, concept_id: int,
                     dimension: str, rule_type: str, severity: str,
                     row_count: int | None, violation_count: int | None,
                     violation_rate: float | None, status: str,
                     error_message: str | None, rule_parameter: dict | None,
                     violation_patterns: list | None,
                     diagnostic_text: str | None) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_issues
                  (tenant_id, scan_id, profile_id, connection_id, schema_name, table_name,
                   column_name, active_rule_id, concept_id,
                   dimension, rule_type, severity,
                   row_count, violation_count, violation_rate,
                   status, error_message, rule_parameter,
                   violation_patterns, diagnostic_text)
               VALUES ($1, $2, $3, $4, $5, $6,
                       $7, $8, $9,
                       $10, $11, $12,
                       $13, $14, $15,
                       $16, $17, $18::jsonb,
                       $19::jsonb, $20)
               ON CONFLICT (scan_id, active_rule_id) DO UPDATE SET
                   row_count          = EXCLUDED.row_count,
                   violation_count    = EXCLUDED.violation_count,
                   violation_rate     = EXCLUDED.violation_rate,
                   status             = EXCLUDED.status,
                   error_message      = EXCLUDED.error_message,
                   rule_parameter     = EXCLUDED.rule_parameter,
                   violation_patterns = EXCLUDED.violation_patterns,
                   diagnostic_text    = EXCLUDED.diagnostic_text
            RETURNING *""",
            (tenant_id, scan_id, profile_id, connection_id, schema_name, table_name,
             column_name, active_rule_id, concept_id,
             dimension, rule_type, severity,
             row_count, violation_count, violation_rate,
             status, (error_message or "")[:8000] or None,
             json.dumps(rule_parameter or {}),
             json.dumps(violation_patterns or []),
             (diagnostic_text or "")[:2000] or None),
        )

    async def find_by_id(self, issue_id: int, tenant_id: int) -> dict | None:
        """Fetch a single issue by id (scoped by tenant). Used by the
        violator-examples endpoint to look up which (rule, table, column)
        an issue belongs to before running the live-peek probe."""
        return await self._fetch_row_optional(
            """SELECT i.*, c.concept AS c_concept
                 FROM dq.t_dq_issues i
                 JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                WHERE i.id = $1 AND i.tenant_id = $2""",
            (issue_id, tenant_id),
        )

    async def find_by_scan(self, scan_id: int, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT i.*, c.concept AS c_concept
                 FROM dq.t_dq_issues i
                 JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                WHERE i.scan_id = $1 AND i.tenant_id = $2
             ORDER BY i.severity, i.column_name, i.dimension""",
            (scan_id, tenant_id),
        )

    async def list_for_profile(
        self, *, tenant_id: int, profile_id: int,
        latest_scan_only: bool = True, limit: int = 500,
    ) -> list[dict]:
        if latest_scan_only:
            return await self._fetch_all(
                """WITH latest AS (
                      SELECT id FROM dq.t_dq_scans
                       WHERE tenant_id = $1 AND profile_id = $2
                         AND status = 'success'
                    ORDER BY finished_at DESC NULLS LAST
                       LIMIT 1
                   )
                   SELECT i.*, c.concept AS c_concept
                     FROM dq.t_dq_issues i
                     JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                     JOIN latest l ON l.id = i.scan_id
                    WHERE i.tenant_id = $1
                 ORDER BY i.severity, i.column_name, i.dimension
                    LIMIT $3""",
                (tenant_id, profile_id, limit),
            )
        return await self._fetch_all(
            """SELECT i.*, c.concept AS c_concept
                 FROM dq.t_dq_issues i
                 JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                WHERE i.tenant_id = $1 AND i.profile_id = $2
             ORDER BY i.scan_id DESC, i.severity, i.column_name
                LIMIT $3""",
            (tenant_id, profile_id, limit),
        )

    async def list_for_table(
        self, *, tenant_id: int, connection_id: UUID,
        schema_name: str, table_name: str,
        latest_scan_only: bool = True, limit: int = 500,
    ) -> list[dict]:
        if latest_scan_only:
            return await self._fetch_all(
                """WITH latest AS (
                      SELECT id FROM dq.t_dq_scans
                       WHERE tenant_id = $1 AND connection_id = $2
                         AND schema_name = $3 AND table_name = $4
                         AND status = 'success'
                    ORDER BY finished_at DESC NULLS LAST
                       LIMIT 1
                   )
                   SELECT i.*, c.concept AS c_concept
                     FROM dq.t_dq_issues i
                     JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                     JOIN latest l ON l.id = i.scan_id
                    WHERE i.tenant_id = $1
                 ORDER BY i.severity, i.column_name, i.dimension
                    LIMIT $5""",
                (tenant_id, connection_id, schema_name, table_name, limit),
            )
        return await self._fetch_all(
            """SELECT i.*, c.concept AS c_concept
                 FROM dq.t_dq_issues i
                 JOIN dq.t_dq_concepts c ON c.id = i.concept_id
                WHERE i.tenant_id = $1 AND i.connection_id = $2
                  AND i.schema_name = $3 AND i.table_name = $4
             ORDER BY i.scan_id DESC, i.severity, i.column_name
                LIMIT $5""",
            (tenant_id, connection_id, schema_name, table_name, limit),
        )

    async def summary_for_scan(self, scan_id: int, tenant_id: int) -> dict:
        """Aggregate counts per status / severity for a single scan."""
        rows = await self._fetch_all(
            """SELECT status, severity, COUNT(*) AS n
                 FROM dq.t_dq_issues
                WHERE scan_id = $1 AND tenant_id = $2
             GROUP BY status, severity""",
            (scan_id, tenant_id),
        )
        out = {"total": 0, "by_status": {}, "by_severity": {}}
        for r in rows:
            out["total"] += int(r["n"])
            out["by_status"][r["status"]] = out["by_status"].get(r["status"], 0) + int(r["n"])
            out["by_severity"][r["severity"]] = out["by_severity"].get(r["severity"], 0) + int(r["n"])
        return out
