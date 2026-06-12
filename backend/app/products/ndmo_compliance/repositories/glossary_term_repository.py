"""GlossaryTermRepository — async access to terms, versions, and relations.

All access to ndmo.t_glossary_terms, ndmo.t_glossary_term_versions, and
ndmo.t_glossary_term_relations.  tenant_id is threaded through every query.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from app.products.ndmo_compliance.entities.glossary_term import GlossaryTerm
from app.products.ndmo_compliance.enums.glossary_source import GlossaryTermSource
from app.products.ndmo_compliance.enums.glossary_status import GlossaryTermStatus
from app.products.ndmo_compliance.enums.glossary_term_type import GlossaryTermType
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)

_COLS = """
    id, tenant_id, domain_id, name_en, name_ar, definition_en, definition_ar,
    acronym, examples, business_rule, status, term_type, source,
    owner_user_id, steward_user_id, created_by, version, published_version_id,
    pending_version_id, deprecation_reason, replaced_by_term_id,
    created_at, updated_at, approved_at, deprecated_at
"""


class GlossaryTermRepository(PostgresqlAsyncRepository):
    # ---- term writes ----------------------------------------------------

    async def create(
        self, *, tenant_id: int, name_en: str, created_by: int,
        domain_id: UUID | None, term_type: str, source: str = "manual",
        name_ar: str | None = None, definition_en: str | None = None,
        definition_ar: str | None = None, acronym: str | None = None,
        examples: str | None = None, business_rule: str | None = None,
        steward_user_id: int | None = None, import_batch_id: UUID | None = None,
    ) -> GlossaryTerm:
        row = await self._fetch_row(
            f"""
            INSERT INTO ndmo.t_glossary_terms
                (tenant_id, domain_id, name_en, name_ar, definition_en,
                 definition_ar, acronym, examples, business_rule, term_type,
                 source, steward_user_id, created_by, import_batch_id,
                 status, version)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'draft',1)
            RETURNING {_COLS}
            """,
            (tenant_id, domain_id, name_en, name_ar, definition_en,
             definition_ar, acronym, examples, business_rule, term_type,
             source, steward_user_id, created_by, import_batch_id),
        )
        return self._row_to_entity(row)

    async def delete_import_batch(
        self, *, tenant_id: int, batch_id: UUID
    ) -> int:
        """Roll back a bulk import — delete its still-draft rows.  Returns the
        number deleted (terms already submitted/approved are left intact)."""
        result = await self._execute(
            "DELETE FROM ndmo.t_glossary_terms "
            "WHERE tenant_id = $1 AND import_batch_id = $2 AND status = 'draft'",
            (tenant_id, batch_id),
        )
        return int(result.split()[-1]) if result else 0

    async def list_approved_for_export(
        self, *, tenant_id: int, domain_ids: list[UUID] | None = None
    ) -> list[dict]:
        """Approved terms joined to their domain name, for Excel export."""
        if domain_ids:
            return await self._fetch_all(
                """
                SELECT t.name_en, t.name_ar, t.definition_en, t.definition_ar,
                       t.acronym, t.term_type, t.version, t.approved_at,
                       d.name_en AS domain_name, t.owner_user_id
                FROM ndmo.t_glossary_terms t
                LEFT JOIN ndmo.t_glossary_domains d ON d.id = t.domain_id
                WHERE t.tenant_id = $1 AND t.status = 'approved'
                  AND t.domain_id = ANY($2::uuid[])
                ORDER BY d.name_en NULLS FIRST, t.name_en
                """,
                (tenant_id, domain_ids),
            )
        return await self._fetch_all(
            """
            SELECT t.name_en, t.name_ar, t.definition_en, t.definition_ar,
                   t.acronym, t.term_type, t.version, t.approved_at,
                   d.name_en AS domain_name, t.owner_user_id
            FROM ndmo.t_glossary_terms t
            LEFT JOIN ndmo.t_glossary_domains d ON d.id = t.domain_id
            WHERE t.tenant_id = $1 AND t.status = 'approved'
            ORDER BY d.name_en NULLS FIRST, t.name_en
            """,
            (tenant_id,),
        )

    async def update_fields(
        self, *, term_id: UUID, tenant_id: int, **fields
    ) -> GlossaryTerm:
        """Patch editable content fields (used while a term is in draft)."""
        allowed = {
            "name_en", "name_ar", "definition_en", "definition_ar",
            "acronym", "examples", "business_rule",
        }
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not sets:
            return await self.find_by_id(term_id=term_id, tenant_id=tenant_id)
        assignments = ", ".join(f"{k} = ${i + 3}" for i, k in enumerate(sets))
        row = await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_terms
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (term_id, tenant_id, *sets.values()),
        )
        return self._row_to_entity(row)

    async def set_status(
        self, *, term_id: UUID, tenant_id: int, status: str,
        approved_at_now: bool = False,
    ) -> GlossaryTerm:
        extra = ", approved_at = CURRENT_TIMESTAMP" if approved_at_now else ""
        row = await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_terms
            SET status = $3, updated_at = CURRENT_TIMESTAMP {extra}
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (term_id, tenant_id, status),
        )
        return self._row_to_entity(row)

    async def deprecate(
        self, *, term_id: UUID, tenant_id: int, reason: str,
        replaced_by_term_id: UUID | None = None,
    ) -> GlossaryTerm:
        row = await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_terms
            SET status = 'deprecated', deprecation_reason = $3,
                replaced_by_term_id = $4, deprecated_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (term_id, tenant_id, reason, replaced_by_term_id),
        )
        return self._row_to_entity(row)

    async def bump_version_and_approve(
        self, *, term_id: UUID, tenant_id: int, new_version: int,
        published_version_id: UUID,
    ) -> GlossaryTerm:
        row = await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_terms
            SET status = 'approved', version = $3,
                published_version_id = $4, pending_version_id = NULL,
                approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (term_id, tenant_id, new_version, published_version_id),
        )
        return self._row_to_entity(row)

    async def delete(self, *, term_id: UUID, tenant_id: int) -> bool:
        result = await self._execute(
            "DELETE FROM ndmo.t_glossary_terms WHERE id = $1 AND tenant_id = $2 "
            "AND status IN ('draft', 'changes_requested')",
            (term_id, tenant_id),
        )
        return self._deleted_successfully(result)

    # ---- term reads -----------------------------------------------------

    async def find_by_id(self, *, term_id: UUID, tenant_id: int) -> GlossaryTerm:
        row = await self._fetch_row(
            f"SELECT {_COLS} FROM ndmo.t_glossary_terms "
            f"WHERE id = $1 AND tenant_id = $2",
            (term_id, tenant_id),
        )
        return self._row_to_entity(row)

    async def list_terms(
        self, *, tenant_id: int, domain_id: UUID | None = None,
        domain_ids: list[UUID] | None = None, status: str | None = None,
        term_type: str | None = None, search: str | None = None,
        include_deprecated: bool = False, limit: int = 200, offset: int = 0,
    ) -> list[GlossaryTerm]:
        conds = ["tenant_id = $1"]
        args: list = [tenant_id]

        def _p() -> str:
            # Called *after* the value is appended, so it refers to the last arg.
            return f"${len(args)}"

        if domain_id is not None:
            args.append(domain_id)
            conds.append(f"domain_id = {_p()}")
        if domain_ids:
            args.append(domain_ids)
            conds.append(f"domain_id = ANY({_p()}::uuid[])")
        if status is not None:
            args.append(status)
            conds.append(f"status = {_p()}")
        elif not include_deprecated:
            conds.append("status <> 'deprecated'")
        if term_type is not None:
            args.append(term_type)
            conds.append(f"term_type = {_p()}")
        if search:
            args.append(f"%{search}%")
            p = _p()
            conds.append(
                f"(name_en ILIKE {p} OR name_ar ILIKE {p} OR acronym ILIKE {p} "
                f"OR definition_en ILIKE {p})"
            )
        args.extend([limit, offset])
        rows = await self._fetch_all(
            f"""
            SELECT {_COLS} FROM ndmo.t_glossary_terms
            WHERE {' AND '.join(conds)}
            ORDER BY name_en
            LIMIT ${len(args) - 1} OFFSET ${len(args)}
            """,
            tuple(args),
        )
        return [self._row_to_entity(r) for r in rows]

    async def find_duplicate(
        self, *, tenant_id: int, domain_id: UUID | None, name_en: str
    ) -> GlossaryTerm | None:
        """Case-insensitive name match in the same domain (BRD FR-036)."""
        if domain_id is None:
            row = await self._fetch_row_optional(
                f"SELECT {_COLS} FROM ndmo.t_glossary_terms "
                f"WHERE tenant_id = $1 AND domain_id IS NULL "
                f"AND lower(name_en) = lower($2) LIMIT 1",
                (tenant_id, name_en),
            )
        else:
            row = await self._fetch_row_optional(
                f"SELECT {_COLS} FROM ndmo.t_glossary_terms "
                f"WHERE tenant_id = $1 AND domain_id = $2 "
                f"AND lower(name_en) = lower($3) LIMIT 1",
                (tenant_id, domain_id, name_en),
            )
        return self._row_to_entity(row) if row else None

    async def count_under_review_for_domains(
        self, *, tenant_id: int, domain_ids: list[UUID], include_enterprise: bool
    ) -> int:
        """Pending-approval count driving the Review Queue sidebar badge."""
        if include_enterprise:
            row = await self._fetch_row_optional(
                "SELECT COUNT(*) AS n FROM ndmo.t_glossary_terms "
                "WHERE tenant_id = $1 AND status = 'under_review' "
                "AND (domain_id = ANY($2::uuid[]) OR term_type = 'enterprise')",
                (tenant_id, domain_ids or []),
            )
        else:
            row = await self._fetch_row_optional(
                "SELECT COUNT(*) AS n FROM ndmo.t_glossary_terms "
                "WHERE tenant_id = $1 AND status = 'under_review' "
                "AND domain_id = ANY($2::uuid[])",
                (tenant_id, domain_ids or []),
            )
        return int(row["n"]) if row else 0

    # ---- versions -------------------------------------------------------

    async def add_version(
        self, *, tenant_id: int, term_id: UUID, version: int,
        snapshot: dict, changed_by: int,
    ) -> UUID:
        return await self._fetch_value(
            """
            INSERT INTO ndmo.t_glossary_term_versions
                (tenant_id, term_id, version, snapshot, changed_by)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (term_id, version) DO UPDATE SET snapshot = EXCLUDED.snapshot
            RETURNING id
            """,
            (tenant_id, term_id, version, json.dumps(snapshot), changed_by),
        )

    async def list_versions(self, *, term_id: UUID, tenant_id: int) -> list[dict]:
        rows = await self._fetch_all(
            "SELECT id, version, snapshot, changed_by, changed_at "
            "FROM ndmo.t_glossary_term_versions "
            "WHERE term_id = $1 AND tenant_id = $2 ORDER BY version DESC",
            (term_id, tenant_id),
        )
        # asyncpg returns JSONB as a string unless a codec is registered;
        # decode the snapshot so callers (and the API) get a real dict.
        for r in rows:
            if isinstance(r.get("snapshot"), str):
                r["snapshot"] = json.loads(r["snapshot"])
        return rows

    # ---- relations ------------------------------------------------------

    async def add_relation(
        self, *, tenant_id: int, source_term_id: UUID, target_term_id: UUID,
        relation_type: str,
    ) -> UUID:
        return await self._fetch_value(
            """
            INSERT INTO ndmo.t_glossary_term_relations
                (tenant_id, source_term_id, target_term_id, relation_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (source_term_id, target_term_id, relation_type) DO NOTHING
            RETURNING id
            """,
            (tenant_id, source_term_id, target_term_id, relation_type),
        )

    async def remove_relation(
        self, *, tenant_id: int, relation_id: UUID
    ) -> None:
        await self._execute(
            "DELETE FROM ndmo.t_glossary_term_relations "
            "WHERE id = $1 AND tenant_id = $2",
            (relation_id, tenant_id),
        )

    async def list_relations(self, *, term_id: UUID, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """
            SELECT r.id, r.relation_type, r.source_term_id, r.target_term_id,
                   t.name_en AS target_name_en, t.name_ar AS target_name_ar
            FROM ndmo.t_glossary_term_relations r
            JOIN ndmo.t_glossary_terms t ON t.id = r.target_term_id
            WHERE r.tenant_id = $1 AND r.source_term_id = $2
            ORDER BY r.created_at
            """,
            (tenant_id, term_id),
        )

    # ---- mapping --------------------------------------------------------

    @staticmethod
    def _row_to_entity(row: dict) -> GlossaryTerm:
        return GlossaryTerm(
            id=row["id"],
            tenant_id=row["tenant_id"],
            domain_id=row["domain_id"],
            name_en=row["name_en"],
            name_ar=row["name_ar"],
            definition_en=row["definition_en"],
            definition_ar=row["definition_ar"],
            acronym=row["acronym"],
            examples=row["examples"],
            business_rule=row["business_rule"],
            status=GlossaryTermStatus(row["status"]),
            term_type=GlossaryTermType(row["term_type"]),
            source=GlossaryTermSource(row["source"]),
            owner_user_id=row["owner_user_id"],
            steward_user_id=row["steward_user_id"],
            created_by=row["created_by"],
            version=row["version"],
            published_version_id=row["published_version_id"],
            pending_version_id=row["pending_version_id"],
            deprecation_reason=row["deprecation_reason"],
            replaced_by_term_id=row["replaced_by_term_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            deprecated_at=row["deprecated_at"],
        )
