"""Persistence for dq.t_dq_references + dq.t_dq_reference_values.

A reference is a named reusable list of allowed values (e.g. "Saudi Banks",
"GCC Countries"). Concepts with ``rule_type='dictionary_match'`` point at a
reference via ``parameter.reference_id`` and the validator fetches the
allowed values at scan time.
"""
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ReferenceRepository(PostgresqlAsyncRepository):

    # ------------------------------------------------------------------
    # References (parent rows)
    # ------------------------------------------------------------------

    async def find_by_tenant(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT r.id, r.tenant_id, r.name, r.description, r.case_sensitive,
                      r.is_seed, r.created_at, r.updated_at, r.created_by,
                      (SELECT COUNT(*) FROM dq.t_dq_reference_values v
                        WHERE v.reference_id = r.id) AS value_count
                 FROM dq.t_dq_references r
                WHERE r.tenant_id = $1
             ORDER BY r.name""",
            (tenant_id,),
        )

    async def find_by_id(self, reference_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_references
                WHERE id = $1 AND tenant_id = $2""",
            (reference_id, tenant_id),
        )

    async def find_by_name(self, tenant_id: int, name: str) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_references
                WHERE tenant_id = $1 AND name = $2""",
            (tenant_id, name),
        )

    async def insert(
        self, *, tenant_id: int, name: str, description: str | None,
        case_sensitive: bool, is_seed: bool, created_by: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_references
                  (tenant_id, name, description, case_sensitive, is_seed, created_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               RETURNING *""",
            (tenant_id, name, description, case_sensitive, is_seed, created_by),
        )

    async def update(
        self, reference_id: int, tenant_id: int, *,
        name: str | None = None, description: str | None = None,
        case_sensitive: bool | None = None,
    ) -> dict:
        sets: list[str] = ["is_seed = FALSE", "updated_at = CURRENT_TIMESTAMP"]
        args: list = [reference_id, tenant_id]
        if name is not None:
            args.append(name);            sets.append(f"name = ${len(args)}")
        if description is not None:
            args.append(description);     sets.append(f"description = ${len(args)}")
        if case_sensitive is not None:
            args.append(case_sensitive);  sets.append(f"case_sensitive = ${len(args)}")
        return await self._fetch_row(
            f"""UPDATE dq.t_dq_references
                   SET {', '.join(sets)}
                 WHERE id = $1 AND tenant_id = $2
             RETURNING *""",
            tuple(args),
        )

    async def delete(self, reference_id: int, tenant_id: int) -> str:
        return await self._execute(
            """DELETE FROM dq.t_dq_references
                WHERE id = $1 AND tenant_id = $2""",
            (reference_id, tenant_id),
        )

    async def find_delete_blockers(self, reference_id: int, tenant_id: int) -> dict:
        """Count concepts whose parameter.reference_id points at this
        reference. Deleting a reference that's still in use would silently
        break those concepts at scan time, so we refuse with a clear error
        and let the user re-point first."""
        rows = await self._fetch_all(
            """SELECT id, dimension, concept
                 FROM dq.t_dq_concepts
                WHERE tenant_id = $1
                  AND rule_type = 'dictionary_match'
                  AND (parameter ->> 'reference_id')::INTEGER = $2""",
            (tenant_id, reference_id),
        )
        return {
            "concept_count": len(rows),
            "concepts": [dict(r) for r in rows],
        }

    # ------------------------------------------------------------------
    # Values (child rows)
    # ------------------------------------------------------------------

    async def list_values(self, reference_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT id, reference_id, value, created_at
                 FROM dq.t_dq_reference_values
                WHERE reference_id = $1
             ORDER BY value""",
            (reference_id,),
        )

    async def list_values_for_validator(self, reference_id: int) -> list[str]:
        """Hot-path helper for the validator — returns the raw value strings
        only, ordered for deterministic IN-clause generation."""
        rows = await self._fetch_all(
            """SELECT value FROM dq.t_dq_reference_values
                WHERE reference_id = $1 ORDER BY value""",
            (reference_id,),
        )
        return [r["value"] for r in rows]

    async def replace_values(self, reference_id: int, values: list[str]) -> int:
        """Bulk-replace: drop all existing values and insert the new set.
        Returns the count of inserted values. Idempotent — calling twice
        with the same list ends up in the same state."""
        await self._execute(
            "DELETE FROM dq.t_dq_reference_values WHERE reference_id = $1",
            (reference_id,),
        )
        if not values:
            return 0
        # UNIQUE(reference_id, value) — dedupe on insert too.
        await self._execute_many(
            """INSERT INTO dq.t_dq_reference_values (reference_id, value)
               VALUES ($1, $2)
               ON CONFLICT (reference_id, value) DO NOTHING""",
            [(reference_id, v) for v in values],
        )
        count = await self._fetch_value(
            "SELECT COUNT(*) FROM dq.t_dq_reference_values WHERE reference_id = $1",
            (reference_id,),
        )
        return int(count or 0)

    async def delete_value(self, value_id: int, reference_id: int) -> str:
        return await self._execute(
            """DELETE FROM dq.t_dq_reference_values
                WHERE id = $1 AND reference_id = $2""",
            (value_id, reference_id),
        )

    # ------------------------------------------------------------------
    # Seed-time helpers
    # ------------------------------------------------------------------

    async def upsert_seed_reference(
        self, *, tenant_id: int, name: str, description: str | None,
        case_sensitive: bool,
    ) -> dict:
        """Insert if missing; return the row. Used by the seed loader."""
        existing = await self.find_by_name(tenant_id, name)
        if existing:
            return existing
        return await self.insert(
            tenant_id=tenant_id, name=name, description=description,
            case_sensitive=case_sensitive, is_seed=True, created_by=None,
        )
