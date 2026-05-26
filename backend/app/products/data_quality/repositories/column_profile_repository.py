"""Persistence for dq.t_dq_column_profiles — per-column statistics per scan."""
import json
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ColumnProfileRepository(PostgresqlAsyncRepository):

    async def insert(self, *, scan_id: int, tenant_id: int, connection_id: UUID,
                     schema_name: str, table_name: str, profile: dict) -> None:
        """Insert a single column-profile row. `profile` is the dict produced
        by ProfilerService._profile_column().

        Stores metadata only — no raw row values from the source. The
        dropped fields (min/max value, top values, sample values) are
        replaced by pattern signatures (dominant_pattern, top_patterns)."""
        await self._execute(
            """INSERT INTO dq.t_dq_column_profiles
                  (scan_id, tenant_id, connection_id, schema_name, table_name,
                   column_name, ordinal_position, declared_data_type, type_category,
                   row_count, non_null_count, null_count, null_rate,
                   pseudo_null_count, pseudo_null_rate,
                   distinct_count, distinct_rate,
                   mean_value, stddev_value, median_value,
                   min_length, max_length, avg_length,
                   dominant_pattern, pattern_conformance_rate, top_patterns,
                   inferred_column_type, raw_metrics)
               VALUES ($1, $2, $3, $4, $5,
                       $6, $7, $8, $9,
                       $10, $11, $12, $13,
                       $14, $15,
                       $16, $17,
                       $18, $19, $20,
                       $21, $22, $23,
                       $24, $25, $26::jsonb,
                       $27, $28::jsonb)
               ON CONFLICT (scan_id, column_name) DO UPDATE SET
                   ordinal_position         = EXCLUDED.ordinal_position,
                   declared_data_type       = EXCLUDED.declared_data_type,
                   type_category            = EXCLUDED.type_category,
                   row_count                = EXCLUDED.row_count,
                   non_null_count           = EXCLUDED.non_null_count,
                   null_count               = EXCLUDED.null_count,
                   null_rate                = EXCLUDED.null_rate,
                   pseudo_null_count        = EXCLUDED.pseudo_null_count,
                   pseudo_null_rate         = EXCLUDED.pseudo_null_rate,
                   distinct_count           = EXCLUDED.distinct_count,
                   distinct_rate            = EXCLUDED.distinct_rate,
                   mean_value               = EXCLUDED.mean_value,
                   stddev_value             = EXCLUDED.stddev_value,
                   median_value             = EXCLUDED.median_value,
                   min_length               = EXCLUDED.min_length,
                   max_length               = EXCLUDED.max_length,
                   avg_length               = EXCLUDED.avg_length,
                   dominant_pattern         = EXCLUDED.dominant_pattern,
                   pattern_conformance_rate = EXCLUDED.pattern_conformance_rate,
                   top_patterns             = EXCLUDED.top_patterns,
                   inferred_column_type     = EXCLUDED.inferred_column_type,
                   raw_metrics              = EXCLUDED.raw_metrics""",
            (
                scan_id, tenant_id, connection_id, schema_name, table_name,
                profile["column_name"], profile.get("ordinal_position"),
                profile.get("declared_data_type"), profile.get("type_category"),
                profile.get("row_count"), profile.get("non_null_count"),
                profile.get("null_count"), profile.get("null_rate"),
                profile.get("pseudo_null_count"), profile.get("pseudo_null_rate"),
                profile.get("distinct_count"), profile.get("distinct_rate"),
                profile.get("mean_value"), profile.get("stddev_value"),
                profile.get("median_value"),
                profile.get("min_length"), profile.get("max_length"),
                profile.get("avg_length"),
                profile.get("dominant_pattern"),
                profile.get("pattern_conformance_rate"),
                json.dumps(profile.get("top_patterns") or []),
                profile.get("inferred_column_type"),
                json.dumps(profile.get("raw_metrics") or {}),
            ),
        )

    async def find_by_scan(self, scan_id: int, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT * FROM dq.t_dq_column_profiles
                WHERE scan_id = $1 AND tenant_id = $2
             ORDER BY ordinal_position NULLS LAST, column_name""",
            (scan_id, tenant_id),
        )

    async def find_latest_for_table(
        self, connection_id: UUID, schema_name: str, table_name: str, tenant_id: int,
    ) -> list[dict]:
        """Latest column profiles for a (schema, table) on the given connection.
        Joins on t_dq_scans to pick the most recent successful scan."""
        return await self._fetch_all(
            """WITH latest AS (
                  SELECT id FROM dq.t_dq_scans
                   WHERE connection_id = $1 AND schema_name = $2 AND table_name = $3
                     AND tenant_id = $4 AND status = 'success'
                ORDER BY finished_at DESC NULLS LAST
                   LIMIT 1
               )
               SELECT p.* FROM dq.t_dq_column_profiles p
                JOIN latest l ON p.scan_id = l.id
             ORDER BY p.ordinal_position NULLS LAST, p.column_name""",
            (connection_id, schema_name, table_name, tenant_id),
        )
