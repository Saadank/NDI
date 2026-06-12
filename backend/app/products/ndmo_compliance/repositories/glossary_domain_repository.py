"""GlossaryDomainRepository — async CRUD on the domain hierarchy.

All access to ndmo.t_glossary_domains and ndmo.t_glossary_domain_stewards.
Every query takes ``tenant_id`` explicitly and filters on it (Datarix-Mono
convention — no per-tenant schema).

This repository is also the source of truth for the domain-scoped RBAC
model: ``owned_domain_ids`` / ``steward_domain_ids`` resolve a user's
glossary role from which domains they own or steward.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.products.ndmo_compliance.entities.glossary_domain import GlossaryDomain
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)

_COLS = """
    id, tenant_id, parent_id, name_en, name_ar, description_en, description_ar,
    owner_user_id, status, created_by, created_at, updated_at
"""


class GlossaryDomainRepository(PostgresqlAsyncRepository):
    # ---- writes ---------------------------------------------------------

    async def create(
        self, *, tenant_id: int, name_en: str, created_by: int,
        parent_id: UUID | None = None, name_ar: str | None = None,
        description_en: str | None = None, description_ar: str | None = None,
        owner_user_id: int | None = None,
    ) -> GlossaryDomain:
        row = await self._fetch_row(
            f"""
            INSERT INTO ndmo.t_glossary_domains
                (tenant_id, parent_id, name_en, name_ar, description_en,
                 description_ar, owner_user_id, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING {_COLS}
            """,
            (tenant_id, parent_id, name_en, name_ar, description_en,
             description_ar, owner_user_id, created_by),
        )
        return self._row_to_entity(row)

    async def update(
        self, *, domain_id: UUID, tenant_id: int, name_en: str | None = None,
        name_ar: str | None = None, description_en: str | None = None,
        description_ar: str | None = None, owner_user_id: int | None = None,
    ) -> GlossaryDomain:
        row = await self._fetch_row(
            f"""
            UPDATE ndmo.t_glossary_domains SET
                name_en        = COALESCE($3, name_en),
                name_ar        = COALESCE($4, name_ar),
                description_en = COALESCE($5, description_en),
                description_ar = COALESCE($6, description_ar),
                owner_user_id  = COALESCE($7, owner_user_id),
                updated_at     = CURRENT_TIMESTAMP
            WHERE id = $1 AND tenant_id = $2
            RETURNING {_COLS}
            """,
            (domain_id, tenant_id, name_en, name_ar, description_en,
             description_ar, owner_user_id),
        )
        return self._row_to_entity(row)

    async def archive(self, *, domain_id: UUID, tenant_id: int) -> None:
        await self._execute(
            """
            UPDATE ndmo.t_glossary_domains
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND tenant_id = $2
            """,
            (domain_id, tenant_id),
        )

    async def add_steward(
        self, *, tenant_id: int, domain_id: UUID, user_id: int, assigned_by: int
    ) -> None:
        await self._execute(
            """
            INSERT INTO ndmo.t_glossary_domain_stewards
                (tenant_id, domain_id, user_id, assigned_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (domain_id, user_id) DO NOTHING
            """,
            (tenant_id, domain_id, user_id, assigned_by),
        )

    async def remove_steward(
        self, *, tenant_id: int, domain_id: UUID, user_id: int
    ) -> None:
        await self._execute(
            """
            DELETE FROM ndmo.t_glossary_domain_stewards
            WHERE tenant_id = $1 AND domain_id = $2 AND user_id = $3
            """,
            (tenant_id, domain_id, user_id),
        )

    # ---- reads ----------------------------------------------------------

    async def find_by_id(
        self, *, domain_id: UUID, tenant_id: int
    ) -> GlossaryDomain:
        row = await self._fetch_row(
            f"SELECT {_COLS} FROM ndmo.t_glossary_domains "
            f"WHERE id = $1 AND tenant_id = $2",
            (domain_id, tenant_id),
        )
        entity = self._row_to_entity(row)
        entity.steward_ids = await self._steward_ids(domain_id)
        return entity

    async def list_all(
        self, *, tenant_id: int, include_archived: bool = False
    ) -> list[GlossaryDomain]:
        """Flat list of every domain for the tenant, hydrated with steward
        ids + approved-term counts.  The service shapes this into a tree."""
        clause = "" if include_archived else "AND d.status = 'active'"
        rows = await self._fetch_all(
            f"""
            SELECT {', '.join('d.' + c.strip() for c in _COLS.split(','))},
                   COALESCE(tc.term_count, 0) AS term_count
            FROM ndmo.t_glossary_domains d
            LEFT JOIN (
                SELECT domain_id, COUNT(*) AS term_count
                FROM ndmo.t_glossary_terms
                WHERE tenant_id = $1 AND status <> 'deprecated'
                GROUP BY domain_id
            ) tc ON tc.domain_id = d.id
            WHERE d.tenant_id = $1 {clause}
            ORDER BY d.name_en
            """,
            (tenant_id,),
        )
        domains = [self._row_to_entity(r) for r in rows]
        for d, r in zip(domains, rows):
            d.term_count = r["term_count"]

        stewards = await self._all_stewards(tenant_id)
        for d in domains:
            d.steward_ids = stewards.get(d.id, [])
        return domains

    # ---- RBAC resolution ------------------------------------------------

    async def owned_domain_ids(
        self, *, tenant_id: int, user_id: int
    ) -> list[UUID]:
        rows = await self._fetch_all(
            "SELECT id FROM ndmo.t_glossary_domains "
            "WHERE tenant_id = $1 AND owner_user_id = $2 AND status = 'active'",
            (tenant_id, user_id),
        )
        return [r["id"] for r in rows]

    async def steward_domain_ids(
        self, *, tenant_id: int, user_id: int
    ) -> list[UUID]:
        rows = await self._fetch_all(
            "SELECT domain_id FROM ndmo.t_glossary_domain_stewards "
            "WHERE tenant_id = $1 AND user_id = $2",
            (tenant_id, user_id),
        )
        return [r["domain_id"] for r in rows]

    # ---- assignable users (for owner/steward pickers) -------------------

    async def list_users(
        self, *, tenant_id: int, search: str | None = None
    ) -> list[dict]:
        if search:
            return await self._fetch_all(
                """
                SELECT id, first_name, last_name, email
                FROM public.t_users
                WHERE tenant_id = $1 AND is_active = TRUE
                  AND (first_name ILIKE $2 OR last_name ILIKE $2 OR email ILIKE $2)
                ORDER BY first_name NULLS LAST, last_name NULLS LAST
                LIMIT 50
                """,
                (tenant_id, f"%{search}%"),
            )
        return await self._fetch_all(
            """
            SELECT id, first_name, last_name, email
            FROM public.t_users
            WHERE tenant_id = $1 AND is_active = TRUE
            ORDER BY first_name NULLS LAST, last_name NULLS LAST
            LIMIT 200
            """,
            (tenant_id,),
        )

    # ---- helpers --------------------------------------------------------

    async def _steward_ids(self, domain_id: UUID) -> list[int]:
        rows = await self._fetch_all(
            "SELECT user_id FROM ndmo.t_glossary_domain_stewards "
            "WHERE domain_id = $1 ORDER BY assigned_at",
            (domain_id,),
        )
        return [r["user_id"] for r in rows]

    async def _all_stewards(self, tenant_id: int) -> dict[UUID, list[int]]:
        rows = await self._fetch_all(
            "SELECT domain_id, user_id FROM ndmo.t_glossary_domain_stewards "
            "WHERE tenant_id = $1 ORDER BY assigned_at",
            (tenant_id,),
        )
        out: dict[UUID, list[int]] = {}
        for r in rows:
            out.setdefault(r["domain_id"], []).append(r["user_id"])
        return out

    @staticmethod
    def _row_to_entity(row: dict) -> GlossaryDomain:
        return GlossaryDomain(
            id=row["id"],
            tenant_id=row["tenant_id"],
            parent_id=row["parent_id"],
            name_en=row["name_en"],
            name_ar=row["name_ar"],
            description_en=row["description_en"],
            description_ar=row["description_ar"],
            owner_user_id=row["owner_user_id"],
            status=row["status"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
