"""Read-only access to the seeded catalog (domains/controls/specifications).

The catalog tables are GLOBAL (no tenant_id) per the Phase-1 schema decision,
so the queries are simple — no tenant filter on the catalog tables, but
every assessment is still scoped to a tenant_id through the cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SpecificationRow:
    """Hydrated row of ndmo.t_ndmo_specifications + parent control + domain."""

    id: int
    code: str
    name_ar: str
    description_ar: str | None
    priority: int
    nca_conditional: bool
    maturity_levels: dict[str, Any]
    required_elements: dict[str, Any]
    acceptance_criteria: str | None
    search_query: str | None
    control_code: str
    control_name_ar: str
    domain_code: str
    domain_name_ar: str


class SpecificationRepository(PostgresqlAsyncRepository):

    async def list_for_cycle(
        self,
        *,
        active_priorities: list[int],
        limit: int | None = None,
    ) -> list[SpecificationRow]:
        """Return every spec whose priority is in the active list, in
        catalog order (domain.sort_order, control.sort_order, spec.sort_order).
        """
        clauses = ["s.priority = ANY($1::smallint[])"]
        args: list[Any] = [active_priorities]
        sql = f"""
            SELECT s.id, s.code, s.name_ar, s.description_ar, s.priority,
                   s.nca_conditional, s.maturity_levels, s.required_elements,
                   s.acceptance_criteria, s.search_query,
                   c.code   AS control_code,
                   c.name_ar AS control_name_ar,
                   d.code   AS domain_code,
                   d.name_ar AS domain_name_ar
              FROM ndmo.t_ndmo_specifications s
              JOIN ndmo.t_ndmo_controls    c ON c.id = s.control_id
              JOIN ndmo.t_ndmo_domains     d ON d.id = c.domain_id
             WHERE {" AND ".join(clauses)}
             ORDER BY d.sort_order, c.sort_order, s.sort_order
        """
        if limit is not None:
            sql += " LIMIT $2"
            args.append(limit)
        rows = await self._fetch_all(sql, tuple(args))
        return [self._row_to_entity(r) for r in rows]

    async def find_by_id(self, *, specification_id: int) -> SpecificationRow:
        row = await self._fetch_row(
            """
            SELECT s.id, s.code, s.name_ar, s.description_ar, s.priority,
                   s.nca_conditional, s.maturity_levels, s.required_elements,
                   s.acceptance_criteria, s.search_query,
                   c.code   AS control_code,
                   c.name_ar AS control_name_ar,
                   d.code   AS domain_code,
                   d.name_ar AS domain_name_ar
              FROM ndmo.t_ndmo_specifications s
              JOIN ndmo.t_ndmo_controls    c ON c.id = s.control_id
              JOIN ndmo.t_ndmo_domains     d ON d.id = c.domain_id
             WHERE s.id = $1
            """,
            (specification_id,),
        )
        return self._row_to_entity(row)

    @staticmethod
    def _row_to_entity(row: dict) -> SpecificationRow:
        import json

        def jl(v: Any) -> dict:
            if v is None:
                return {}
            if isinstance(v, dict):
                return v
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return {}
            return {}

        return SpecificationRow(
            id=row["id"],
            code=row["code"],
            name_ar=row["name_ar"],
            description_ar=row.get("description_ar"),
            priority=row["priority"],
            nca_conditional=row.get("nca_conditional", False),
            maturity_levels=jl(row.get("maturity_levels")),
            required_elements=jl(row.get("required_elements")),
            acceptance_criteria=row.get("acceptance_criteria"),
            search_query=row.get("search_query"),
            control_code=row["control_code"],
            control_name_ar=row["control_name_ar"],
            domain_code=row["domain_code"],
            domain_name_ar=row["domain_name_ar"],
        )
