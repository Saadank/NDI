"""Cycle repository — reads ndmo.t_ndmo_cycles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CycleRow:
    id: int
    tenant_id: int
    year: int
    quarter: int | None
    active_priorities: list[int]
    status: str


class CycleRepository(PostgresqlAsyncRepository):

    async def find_active(self, *, tenant_id: int) -> CycleRow | None:
        """Return the tenant's most recent active cycle, if any."""
        row = await self._fetch_row_optional(
            """
            SELECT id, tenant_id, year, quarter, active_priorities, status
              FROM ndmo.t_ndmo_cycles
             WHERE tenant_id = $1 AND status = 'active'
             ORDER BY year DESC, quarter DESC NULLS LAST
             LIMIT 1
            """,
            (tenant_id,),
        )
        if row is None:
            return None
        return self._row_to_entity(row)

    async def find_by_id(self, *, cycle_id: int, tenant_id: int) -> CycleRow:
        row = await self._fetch_row(
            """
            SELECT id, tenant_id, year, quarter, active_priorities, status
              FROM ndmo.t_ndmo_cycles
             WHERE id = $1 AND tenant_id = $2
            """,
            (cycle_id, tenant_id),
        )
        return self._row_to_entity(row)

    @staticmethod
    def _row_to_entity(row: dict) -> CycleRow:
        ap = row.get("active_priorities") or []
        if not isinstance(ap, list):
            ap = list(ap)
        return CycleRow(
            id=row["id"],
            tenant_id=row["tenant_id"],
            year=row["year"],
            quarter=row.get("quarter"),
            active_priorities=[int(x) for x in ap],
            status=row["status"],
        )
