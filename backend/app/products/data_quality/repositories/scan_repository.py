"""Persistence for dq.t_dq_scans — one row per profiler / validator scan run."""
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ScanRepository(PostgresqlAsyncRepository):

    async def create(
        self, *, tenant_id: int, profile_id: int, connection_id: UUID,
        schema_name: str, table_name: str,
        scan_type: str = "profile", trigger_source: str = "manual",
        triggered_by: int | None = None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_scans
                   (tenant_id, profile_id, connection_id, schema_name, table_name,
                    scan_type, trigger_source, triggered_by, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
               RETURNING *""",
            (tenant_id, profile_id, connection_id, schema_name, table_name,
             scan_type, trigger_source, triggered_by),
        )

    async def mark_running(self, scan_id: int) -> None:
        await self._execute(
            """UPDATE dq.t_dq_scans
                  SET status = 'running', started_at = CURRENT_TIMESTAMP
                WHERE id = $1""",
            (scan_id,),
        )

    async def mark_success(
        self, scan_id: int, *, row_count: int | None, column_count: int | None,
        duration_ms: int,
    ) -> None:
        await self._execute(
            """UPDATE dq.t_dq_scans
                  SET status = 'success',
                      row_count = $2,
                      column_count = $3,
                      duration_ms = $4,
                      finished_at = CURRENT_TIMESTAMP
                WHERE id = $1""",
            (scan_id, row_count, column_count, duration_ms),
        )

    async def mark_failed(self, scan_id: int, error_message: str, duration_ms: int) -> None:
        await self._execute(
            """UPDATE dq.t_dq_scans
                  SET status = 'failed',
                      error_message = $2,
                      duration_ms = $3,
                      finished_at = CURRENT_TIMESTAMP
                WHERE id = $1""",
            (scan_id, error_message[:8000] if error_message else None, duration_ms),
        )

    async def find_by_id(self, scan_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_scans WHERE id = $1 AND tenant_id = $2""",
            (scan_id, tenant_id),
        )

    async def delete_by_id(self, scan_id: int, tenant_id: int) -> str:
        """Hard-delete a scan. CASCADES to t_dq_column_profiles,
        t_dq_issues, and t_dq_score_history via FK ON DELETE CASCADE —
        all of the scan's derived data goes with it. Caller's UI MUST
        surface this in a confirm dialog before sending."""
        return await self._execute(
            """DELETE FROM dq.t_dq_scans
                WHERE id = $1 AND tenant_id = $2""",
            (scan_id, tenant_id),
        )

    async def list_for_tenant(
        self, tenant_id: int, *, profile_id: int | None = None,
        connection_id: UUID | None = None,
        schema_name: str | None = None, table_name: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["tenant_id = $1"]
        args: list = [tenant_id]
        if profile_id is not None:
            args.append(profile_id)
            clauses.append(f"profile_id = ${len(args)}")
        if connection_id is not None:
            args.append(connection_id)
            clauses.append(f"connection_id = ${len(args)}")
        if schema_name is not None:
            args.append(schema_name)
            clauses.append(f"schema_name = ${len(args)}")
        if table_name is not None:
            args.append(table_name)
            clauses.append(f"table_name = ${len(args)}")
        args.append(limit)
        return await self._fetch_all(
            f"""SELECT * FROM dq.t_dq_scans
                 WHERE {' AND '.join(clauses)}
              ORDER BY created_at DESC
                 LIMIT ${len(args)}""",
            tuple(args),
        )
