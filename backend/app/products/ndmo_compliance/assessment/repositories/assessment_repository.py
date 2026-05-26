"""Writes to ndmo.t_ndmo_assessments + ndmo.t_ndmo_citations.

Idempotent UPSERT on (tenant_id, specification_id, cycle_id) per the
schema's UNIQUE constraint.  Citations are wiped + re-inserted for each
re-run (delete-then-insert inside a transaction).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from uuid import UUID

from app.products.ndmo_compliance.assessment.output_schema import AssessmentOutput
from app.products.ndmo_compliance.enums.assessment_status import AssessmentStatus
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AssessmentRow:
    id: UUID
    tenant_id: int
    specification_id: int
    cycle_id: int
    maturity_level: int
    status: AssessmentStatus
    confidence: float | None


class AssessmentRepository(PostgresqlAsyncRepository):

    async def upsert(
        self,
        *,
        tenant_id: int,
        specification_id: int,
        cycle_id: int,
        output: AssessmentOutput,
        prompt_metadata: dict | None = None,
    ) -> UUID:
        """Insert or update the (tenant, spec, cycle) row + replace citations.

        The whole thing runs in one transaction.
        """
        async with self._transaction() as conn:
            ai_result = {
                "rationale_ar": output.rationale_ar,
                "gaps_ar": output.gaps_ar,
                "needs_review": output.needs_review,
                "prompt": prompt_metadata or {},
                "raw_citations": [
                    {
                        "chunk_id": c.chunk_id,
                        "page_number": c.page_number,
                        "source_file": c.source_file,
                        "quoted_text_ar": c.quoted_text_ar,
                        "supports_level": c.supports_level,
                    }
                    for c in output.citations
                ],
            }

            row = await conn.fetchrow(
                """
                INSERT INTO ndmo.t_ndmo_assessments
                    (tenant_id, specification_id, cycle_id, maturity_level,
                     status, confidence, ai_result)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                ON CONFLICT (tenant_id, specification_id, cycle_id) DO UPDATE
                  SET maturity_level = EXCLUDED.maturity_level,
                      status         = EXCLUDED.status,
                      confidence     = EXCLUDED.confidence,
                      ai_result      = EXCLUDED.ai_result,
                      updated_at     = CURRENT_TIMESTAMP
                RETURNING id
                """,
                tenant_id, specification_id, cycle_id, output.maturity_level,
                self._derived_status(output).value, output.confidence,
                json.dumps(ai_result, ensure_ascii=False, default=str),
            )
            assessment_id: UUID = row["id"]

            # Wipe and re-insert citations.
            await conn.execute(
                "DELETE FROM ndmo.t_ndmo_citations WHERE assessment_id = $1",
                assessment_id,
            )
            if output.citations:
                await conn.executemany(
                    """
                    INSERT INTO ndmo.t_ndmo_citations
                        (assessment_id, chunk_id, citation_text, source_file,
                         page_number, confidence)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    [
                        (
                            assessment_id,
                            c.chunk_id,
                            c.quoted_text_ar,
                            c.source_file,
                            c.page_number,
                            None,
                        )
                        for c in output.citations
                    ],
                )
            return assessment_id

    @staticmethod
    def _derived_status(output: AssessmentOutput) -> AssessmentStatus:
        """Engine-output → DB status mapping.

        Every engine verdict enters UNDER_REVIEW.  The Compliance Analyst
        is the only role that can move a row to APPROVED or REJECTED via
        POST /assessments/{id}/review — the engine never auto-approves.
        ``output.needs_review`` is preserved inside ai_result so the
        Dashboard can surface low-confidence rows at the top of the
        analyst's queue.
        """
        del output  # unused — kept in the signature for future tuning hooks
        return AssessmentStatus.UNDER_REVIEW
