"""HTTP-side facade around AssessmentEngine.

Endpoints (in routers/assessments.py):
  * POST /assessments/run            — kick off a full-cycle run (async)
  * GET  /assessments/{spec_id}      — fetch one verdict + citations
  * GET  /assessments                — list the current cycle's verdicts
  * POST /assessments/{spec_id}/review — analyst approves/rejects/edits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.products.ndmo_compliance.assessment.engine import AssessmentEngine
from app.products.ndmo_compliance.assessment.repositories.cycle_repository import (
    CycleRepository,
)
from app.products.ndmo_compliance.enums.assessment_status import AssessmentStatus
from app.products.ndmo_compliance.enums.review_decision import ReviewDecision
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunStarted:
    cycle_id: int
    total_specs: int
    dry_run: bool


class AssessmentService(PostgresqlAsyncRepository):
    def __init__(self) -> None:
        self._cycles = CycleRepository()

    async def trigger_run(
        self,
        *,
        auth_user: AuthUser,
        cycle_id: int | None = None,
        dry_run: bool = False,
        spec_limit: int | None = None,
    ) -> RunStarted:
        """Synchronously kick off the engine.  Phase 4 will move this to a
        background queue; for now we run inline so the caller gets the
        summary back immediately (acceptable since one cycle takes a few
        minutes with concurrency=8).
        """
        engine = AssessmentEngine()
        result = await engine.run_cycle(
            tenant_id=auth_user.tenant_id,
            cycle_id=cycle_id,
            dry_run=dry_run,
            spec_limit=spec_limit,
        )
        return RunStarted(
            cycle_id=result.cycle_id,
            total_specs=result.total,
            dry_run=dry_run,
        )

    async def list_for_active_cycle(
        self, *, auth_user: AuthUser, status: str | None = None,
        limit: int = 200, offset: int = 0,
    ) -> list[dict[str, Any]]:
        cycle = await self._cycles.find_active(tenant_id=auth_user.tenant_id)
        if cycle is None:
            return []
        args: list[Any] = [auth_user.tenant_id, cycle.id]
        clauses = ["a.tenant_id = $1", "a.cycle_id = $2"]
        if status:
            args.append(status)
            clauses.append(f"a.status = ${len(args)}")
        args.extend([limit, offset])
        rows = await self._fetch_all(
            f"""
            SELECT a.id, a.specification_id, a.maturity_level, a.status,
                   a.confidence, a.updated_at,
                   s.code AS spec_code, s.name_ar, s.priority,
                   c.code AS control_code, d.code AS domain_code
              FROM ndmo.t_ndmo_assessments a
              JOIN ndmo.t_ndmo_specifications s ON s.id = a.specification_id
              JOIN ndmo.t_ndmo_controls       c ON c.id = s.control_id
              JOIN ndmo.t_ndmo_domains        d ON d.id = c.domain_id
             WHERE {" AND ".join(clauses)}
             ORDER BY d.sort_order, c.sort_order, s.sort_order
             LIMIT ${len(args) - 1} OFFSET ${len(args)}
            """,
            tuple(args),
        )
        return rows

    async def get_with_citations(
        self, *, assessment_id: UUID, auth_user: AuthUser,
    ) -> dict[str, Any] | None:
        row = await self._fetch_row_optional(
            """
            SELECT a.id, a.specification_id, a.cycle_id, a.maturity_level,
                   a.status, a.confidence, a.ai_result,
                   a.review_decision, a.review_note, a.reviewed_by,
                   a.updated_at,
                   s.code AS spec_code, s.name_ar AS spec_name_ar,
                   s.priority, s.nca_conditional,
                   c.code AS control_code, c.name_ar AS control_name_ar,
                   d.code AS domain_code, d.name_ar AS domain_name_ar
              FROM ndmo.t_ndmo_assessments a
              JOIN ndmo.t_ndmo_specifications s ON s.id = a.specification_id
              JOIN ndmo.t_ndmo_controls       c ON c.id = s.control_id
              JOIN ndmo.t_ndmo_domains        d ON d.id = c.domain_id
             WHERE a.id = $1 AND a.tenant_id = $2
            """,
            (assessment_id, auth_user.tenant_id),
        )
        if row is None:
            return None
        citations = await self._fetch_all(
            """
            SELECT chunk_id, citation_text, source_file, page_number, confidence
              FROM ndmo.t_ndmo_citations
             WHERE assessment_id = $1
             ORDER BY page_number, source_file
            """,
            (assessment_id,),
        )
        row["citations"] = citations
        return row

    async def submit_review(
        self,
        *,
        assessment_id: UUID,
        auth_user: AuthUser,
        decision: ReviewDecision,
        note: str | None,
        override_maturity_level: int | None = None,
    ) -> None:
        final_status = (
            AssessmentStatus.APPROVED if decision == ReviewDecision.APPROVED
            else AssessmentStatus.REJECTED if decision == ReviewDecision.REJECTED
            else AssessmentStatus.UNDER_REVIEW
        )
        if override_maturity_level is not None:
            await self._execute(
                """
                UPDATE ndmo.t_ndmo_assessments
                   SET maturity_level = $1, status = $2,
                       review_decision = $3, review_note = $4,
                       reviewed_by = $5, updated_at = CURRENT_TIMESTAMP
                 WHERE id = $6 AND tenant_id = $7
                """,
                (override_maturity_level, final_status.value, decision.value,
                 note, auth_user.user_id, assessment_id, auth_user.tenant_id),
            )
        else:
            await self._execute(
                """
                UPDATE ndmo.t_ndmo_assessments
                   SET status = $1, review_decision = $2, review_note = $3,
                       reviewed_by = $4, updated_at = CURRENT_TIMESTAMP
                 WHERE id = $5 AND tenant_id = $6
                """,
                (final_status.value, decision.value, note,
                 auth_user.user_id, assessment_id, auth_user.tenant_id),
            )


def get_assessment_service() -> AssessmentService:
    return AssessmentService()
