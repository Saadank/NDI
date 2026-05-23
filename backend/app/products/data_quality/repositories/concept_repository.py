"""Persistence for dq.t_dq_concepts — the per-tenant rule-applicability dictionary."""
import json

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ConceptRepository(PostgresqlAsyncRepository):

    async def find_by_tenant(
        self, tenant_id: int, *, dimension: str | None = None,
        enabled_only: bool = False,
    ) -> list[dict]:
        clauses = ["tenant_id = $1"]
        args: list = [tenant_id]
        if dimension is not None:
            args.append(dimension)
            clauses.append(f"dimension = ${len(args)}")
        if enabled_only:
            clauses.append("enabled = TRUE")
        return await self._fetch_all(
            f"""SELECT id, tenant_id, dimension, concept, synonyms, rule_type,
                       parameter, severity, applies_to_types, notes, enabled,
                       is_seed, created_at, updated_at, created_by
                  FROM dq.t_dq_concepts
                 WHERE {' AND '.join(clauses)}
              ORDER BY dimension, concept""",
            tuple(args),
        )

    async def find_by_id(self, concept_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT * FROM dq.t_dq_concepts WHERE id = $1 AND tenant_id = $2""",
            (concept_id, tenant_id),
        )

    async def insert(
        self, *, tenant_id: int, dimension: str, concept: str,
        synonyms: list[str], rule_type: str, parameter: dict, severity: str,
        applies_to_types: list[str] | None, notes: str | None,
        enabled: bool, is_seed: bool, created_by: int | None,
    ) -> dict:
        return await self._fetch_row(
            """INSERT INTO dq.t_dq_concepts
                  (tenant_id, dimension, concept, synonyms, rule_type, parameter,
                   severity, applies_to_types, notes, enabled, is_seed, created_by)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12)
               RETURNING *""",
            (tenant_id, dimension, concept, synonyms, rule_type,
             json.dumps(parameter or {}), severity,
             applies_to_types, notes, enabled, is_seed, created_by),
        )

    async def update(
        self, concept_id: int, tenant_id: int, *,
        synonyms: list[str] | None = None, rule_type: str | None = None,
        parameter: dict | None = None, severity: str | None = None,
        applies_to_types: list[str] | None = None, notes: str | None = None,
        enabled: bool | None = None,
    ) -> dict:
        # Patch update: each non-None param contributes a SET clause. is_seed
        # flips to FALSE on any user edit (so re-seeding skips this row).
        sets: list[str] = ["is_seed = FALSE", "updated_at = CURRENT_TIMESTAMP"]
        args: list = [concept_id, tenant_id]
        if synonyms is not None:
            args.append(synonyms);                  sets.append(f"synonyms = ${len(args)}")
        if rule_type is not None:
            args.append(rule_type);                 sets.append(f"rule_type = ${len(args)}")
        if parameter is not None:
            args.append(json.dumps(parameter));     sets.append(f"parameter = ${len(args)}::jsonb")
        if severity is not None:
            args.append(severity);                  sets.append(f"severity = ${len(args)}")
        if applies_to_types is not None:
            # An empty list normalizes to SQL NULL ("any semantic type").
            args.append(applies_to_types or None);  sets.append(f"applies_to_types = ${len(args)}")
        if notes is not None:
            args.append(notes);                     sets.append(f"notes = ${len(args)}")
        if enabled is not None:
            args.append(enabled);                   sets.append(f"enabled = ${len(args)}")

        return await self._fetch_row(
            f"""UPDATE dq.t_dq_concepts
                   SET {', '.join(sets)}
                 WHERE id = $1 AND tenant_id = $2
             RETURNING *""",
            tuple(args),
        )

    async def delete(self, concept_id: int, tenant_id: int) -> str:
        return await self._execute(
            """DELETE FROM dq.t_dq_concepts WHERE id = $1 AND tenant_id = $2""",
            (concept_id, tenant_id),
        )

    async def find_delete_blockers(self, concept_id: int, tenant_id: int) -> dict:
        """Counts the issues/scans/profiles that block deletion of this concept.
        The FK on t_dq_issues.concept_id is RESTRICT (unlike active_rule_id,
        which CASCADEs), so any past-scan issue tagged with this concept
        prevents the DELETE. Returns zeros if nothing blocks."""
        row = await self._fetch_row(
            """SELECT COUNT(*)                       AS issue_count,
                      COUNT(DISTINCT scan_id)         AS scan_count,
                      COUNT(DISTINCT profile_id)      AS profile_count,
                      COALESCE(
                        ARRAY_AGG(DISTINCT profile_id) FILTER (WHERE profile_id IS NOT NULL),
                        ARRAY[]::INTEGER[]
                      )                               AS profile_ids
                 FROM dq.t_dq_issues
                WHERE concept_id = $1 AND tenant_id = $2""",
            (concept_id, tenant_id),
        )
        return dict(row)

    async def upsert_seed(
        self, *, tenant_id: int, dimension: str, concept: str,
        synonyms: list[str], rule_type: str, parameter: dict, severity: str,
        applies_to_types: list[str] | None, notes: str | None,
    ) -> str:
        """Insert if missing, do NOTHING if it already exists. Used by the
        seed endpoint — never overwrites a tenant's customized concept."""
        return await self._execute(
            """INSERT INTO dq.t_dq_concepts
                  (tenant_id, dimension, concept, synonyms, rule_type, parameter,
                   severity, applies_to_types, notes, enabled, is_seed)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, TRUE, TRUE)
               ON CONFLICT (tenant_id, dimension, concept) DO NOTHING""",
            (tenant_id, dimension, concept, synonyms, rule_type,
             json.dumps(parameter or {}), severity,
             applies_to_types, notes),
        )

    async def refresh_seed(
        self, *, tenant_id: int, dimension: str, concept: str,
        synonyms: list[str], rule_type: str, parameter: dict, severity: str,
        applies_to_types: list[str] | None, notes: str | None,
    ) -> str:
        """Insert if missing; if it exists AND is still is_seed=TRUE, overwrite
        synonyms/rule_type/parameter/severity/applies_to_types/notes from the
        seed. The WHERE on the DO UPDATE protects user-customized rows
        (is_seed=FALSE), which become no-ops."""
        return await self._execute(
            """INSERT INTO dq.t_dq_concepts
                  (tenant_id, dimension, concept, synonyms, rule_type, parameter,
                   severity, applies_to_types, notes, enabled, is_seed)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, TRUE, TRUE)
               ON CONFLICT (tenant_id, dimension, concept) DO UPDATE
                  SET synonyms         = EXCLUDED.synonyms,
                      rule_type        = EXCLUDED.rule_type,
                      parameter        = EXCLUDED.parameter,
                      severity         = EXCLUDED.severity,
                      applies_to_types = EXCLUDED.applies_to_types,
                      notes            = EXCLUDED.notes,
                      updated_at       = CURRENT_TIMESTAMP
                WHERE dq.t_dq_concepts.is_seed = TRUE""",
            (tenant_id, dimension, concept, synonyms, rule_type,
             json.dumps(parameter or {}), severity,
             applies_to_types, notes),
        )
