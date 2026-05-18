"""Persistence for dq.t_dq_profiles — Profile Assets (Phase 1.5)."""
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ProfileRepository(PostgresqlAsyncRepository):

    async def find_by_id(self, profile_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_profiles WHERE id = $1 AND tenant_id = $2""",
            (profile_id, tenant_id),
        )

    async def find_by_name(self, tenant_id: int, name: str) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_profiles WHERE tenant_id = $1 AND name = $2""",
            (tenant_id, name),
        )

    async def find_by_target(
        self, tenant_id: int, connection_id: UUID,
        schema_name: str, table_name: str,
    ) -> list[dict]:
        """All profiles pointing at the same (conn, schema, table). May be
        multiple — users can keep variants (e.g. strict + lenient thresholds)."""
        return await self._fetch_all(
            """SELECT * FROM dq.t_dq_profiles
                WHERE tenant_id = $1 AND connection_id = $2
                  AND schema_name = $3 AND table_name = $4
             ORDER BY name""",
            (tenant_id, connection_id, schema_name, table_name),
        )

    async def list_for_tenant(
        self, tenant_id: int, *, location_path: str | None = None,
        connection_id: UUID | None = None,
    ) -> list[dict]:
        clauses = ["tenant_id = $1"]
        args: list = [tenant_id]
        if location_path is not None:
            args.append(location_path)
            clauses.append(f"COALESCE(location_path, '') = ${len(args)}")
        if connection_id is not None:
            args.append(connection_id)
            clauses.append(f"connection_id = ${len(args)}")
        return await self._fetch_all(
            f"""SELECT p.*,
                       (SELECT COUNT(*) FROM dq.t_dq_scans s
                          WHERE s.profile_id = p.id) AS scan_count,
                       (SELECT COUNT(*) FROM dq.t_dq_active_rules ar
                          WHERE ar.profile_id = p.id) AS rule_count,
                       (SELECT MAX(s.finished_at) FROM dq.t_dq_scans s
                          WHERE s.profile_id = p.id AND s.status = 'success')
                                                       AS last_scan_at
                  FROM dq.t_dq_profiles p
                 WHERE {' AND '.join(clauses)}
              ORDER BY location_path NULLS FIRST, name""",
            tuple(args),
        )

    async def insert(
        self, *, tenant_id: int, name: str, description: str | None,
        location_path: str | None, connection_id: UUID,
        schema_name: str, table_name: str,
        sampling_mode: str, sample_size: int | None,
        drill_down: bool, ai_enabled: bool,
        selected_columns: list[str] | None,
        created_by: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_profiles
                  (tenant_id, name, description, location_path,
                   connection_id, schema_name, table_name,
                   sampling_mode, sample_size, drill_down, ai_enabled,
                   selected_columns, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            RETURNING *""",
            (tenant_id, name, description, location_path,
             connection_id, schema_name, table_name,
             sampling_mode, sample_size, drill_down, ai_enabled,
             selected_columns, created_by),
        )

    async def update(
        self, profile_id: int, tenant_id: int, *,
        name: str | None = None, description: str | None = None,
        location_path: str | None = None,
        sampling_mode: str | None = None, sample_size: int | None = None,
        drill_down: bool | None = None, ai_enabled: bool | None = None,
        selected_columns: list[str] | None = None,
    ) -> dict:
        # Patch update — each non-None field contributes a SET clause.
        # Connection / schema / table are NOT editable: they define the
        # source binding; changing them would orphan existing scans/rules.
        # Use clone() to point a new profile at a different source.
        sets: list[str] = ["updated_at = CURRENT_TIMESTAMP"]
        args: list = [profile_id, tenant_id]
        if name is not None:
            args.append(name);          sets.append(f"name = ${len(args)}")
        if description is not None:
            args.append(description);   sets.append(f"description = ${len(args)}")
        if location_path is not None:
            args.append(location_path); sets.append(f"location_path = ${len(args)}")
        if sampling_mode is not None:
            args.append(sampling_mode); sets.append(f"sampling_mode = ${len(args)}")
        if sample_size is not None:
            args.append(sample_size);   sets.append(f"sample_size = ${len(args)}")
        if drill_down is not None:
            args.append(drill_down);    sets.append(f"drill_down = ${len(args)}")
        if ai_enabled is not None:
            args.append(ai_enabled);    sets.append(f"ai_enabled = ${len(args)}")
        if selected_columns is not None:
            args.append(selected_columns); sets.append(f"selected_columns = ${len(args)}")

        return await self._fetch_row(
            f"""UPDATE dq.t_dq_profiles
                   SET {', '.join(sets)}
                 WHERE id = $1 AND tenant_id = $2
             RETURNING *""",
            tuple(args),
        )

    async def delete(self, profile_id: int, tenant_id: int) -> str:
        # ON DELETE CASCADE on child tables takes care of scans/rules/issues.
        return await self._execute(
            """DELETE FROM dq.t_dq_profiles WHERE id = $1 AND tenant_id = $2""",
            (profile_id, tenant_id),
        )
