"""Top-level assessment engine.

For a (tenant, cycle) pair, walk every in-scope specification, retrieve
its top-5 evidence chunks via Qdrant hybrid search, ask the LLM for a
structured maturity verdict, and persist.

LLM provider: OpenAI Chat Completions (gpt-4o by default), invoked with
``response_format={"type": "json_schema", ...}`` so the JSON is
model-guaranteed and cannot drift from the schema.

Configuration knobs (env vars, all optional unless noted):
  * OPENAI_API_KEY                (REQUIRED at run-time)
  * OPENAI_BASE_URL               override endpoint (Azure OpenAI,
                                  OpenAI-compatible gateway, ...)
  * NDMO_ASSESSMENT_MODEL         default ``gpt-4o``
  * NDMO_ASSESSMENT_MAX_TOKENS    default 1500
  * NDMO_ASSESSMENT_TIMEOUT_S     default 60
  * NDMO_ASSESSMENT_CONCURRENCY   default 8
  * NDMO_ASSESSMENT_TOP_K         default 5

Failure handling: any spec whose LLM call raises is recorded with
status="error" in the BatchResult.  The engine continues with the next spec.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from app.products.ndmo_compliance.assessment.output_schema import (
    ASSESSMENT_JSON_SCHEMA,
    AssessmentOutput,
)
from app.products.ndmo_compliance.assessment.prompts import (
    SYSTEM_PROMPT_AR,
    build_retrieval_query,
    build_user_prompt,
)
from app.products.ndmo_compliance.assessment.repositories.assessment_repository import (
    AssessmentRepository,
)
from app.products.ndmo_compliance.assessment.repositories.cycle_repository import (
    CycleRepository,
    CycleRow,
)
from app.products.ndmo_compliance.assessment.repositories.specification_repository import (
    SpecificationRepository,
    SpecificationRow,
)
from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.gateways.embedding_gateway import EmbeddingGateway
from app.products.ndmo_compliance.gateways.qdrant_gateway import QdrantGateway

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"


@dataclass(slots=True)
class SpecResult:
    """One spec's outcome in a batch run."""

    spec_id: int
    spec_code: str
    status: str                                # "ok" | "skipped_no_evidence" | "error"
    output: AssessmentOutput | None = None
    error: str | None = None
    retrieved_chunks: int = 0
    latency_ms: int = 0


@dataclass(slots=True)
class BatchResult:
    """Summary of one engine run."""

    cycle_id: int
    tenant_id: int
    started_at: float
    ended_at: float = 0.0
    per_spec: list[SpecResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.per_spec)

    @property
    def ok(self) -> int:
        return sum(1 for r in self.per_spec if r.status == "ok")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.per_spec if r.status == "skipped_no_evidence")

    @property
    def errors(self) -> int:
        return sum(1 for r in self.per_spec if r.status == "error")


class AssessmentEngine:
    """Composes retrieval + LLM + persistence."""

    def __init__(
        self,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
        concurrency: int | None = None,
        top_k: int | None = None,
        openai_client: AsyncOpenAI | None = None,
        qdrant: QdrantGateway | None = None,
        embedder: EmbeddingGateway | None = None,
    ) -> None:
        self.model = model or os.environ.get("NDMO_ASSESSMENT_MODEL", _DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.environ.get("NDMO_ASSESSMENT_MAX_TOKENS", "1500"))
        self.timeout_s = float(timeout_s or os.environ.get("NDMO_ASSESSMENT_TIMEOUT_S", "60"))
        self.concurrency = int(concurrency or os.environ.get("NDMO_ASSESSMENT_CONCURRENCY", "8"))
        self.top_k = int(top_k or os.environ.get("NDMO_ASSESSMENT_TOP_K", "5"))

        # API-key check deferred to .run() so import-time doesn't fail in tests.
        # OPENAI_BASE_URL is honored by the SDK natively (Azure / proxy / etc.).
        self._client = openai_client or AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL") or None,
            timeout=self.timeout_s,
        )
        self._qdrant = qdrant or QdrantGateway()
        self._embedder = embedder or EmbeddingGateway()
        self._specs = SpecificationRepository()
        self._cycles = CycleRepository()
        self._assessments = AssessmentRepository()

    # ---- batch entry point ----------------------------------------------

    async def run_cycle(
        self,
        *,
        tenant_id: int,
        cycle_id: int | None = None,
        dry_run: bool = False,
        spec_limit: int | None = None,
    ) -> BatchResult:
        """Assess every in-scope spec for ``tenant_id`` under ``cycle_id``.

        If ``cycle_id`` is None, the tenant's active cycle is used.
        ``dry_run=True`` skips the DB write (engine.persist).
        ``spec_limit`` caps the spec count for canary runs.
        """
        current_tenant_id.set(tenant_id)

        cycle = (
            await self._cycles.find_by_id(cycle_id=cycle_id, tenant_id=tenant_id)
            if cycle_id is not None
            else await self._cycles.find_active(tenant_id=tenant_id)
        )
        if cycle is None:
            raise RuntimeError(
                f"No active cycle found for tenant_id={tenant_id}.  "
                f"Create one in ndmo.t_ndmo_cycles first."
            )

        specs = await self._specs.list_for_cycle(
            active_priorities=cycle.active_priorities, limit=spec_limit
        )
        logger.info(
            "Assessment engine: tenant=%d cycle=%d active_priorities=%s n_specs=%d dry_run=%s",
            tenant_id, cycle.id, cycle.active_priorities, len(specs), dry_run,
        )

        result = BatchResult(
            cycle_id=cycle.id,
            tenant_id=tenant_id,
            started_at=time.time(),
        )
        sem = asyncio.Semaphore(self.concurrency)

        async def _one(spec: SpecificationRow) -> SpecResult:
            async with sem:
                return await self._assess_one(spec, cycle, dry_run)

        result.per_spec = await asyncio.gather(*(_one(s) for s in specs))
        result.ended_at = time.time()
        return result

    # ---- single-spec assessment -----------------------------------------

    async def _assess_one(
        self, spec: SpecificationRow, cycle: CycleRow, dry_run: bool,
    ) -> SpecResult:
        t0 = time.time()
        try:
            chunks = await self._retrieve_chunks(spec, cycle.tenant_id)
            if not chunks:
                # Persist a level-0 "no evidence" verdict so the UI shows
                # the row instead of silently skipping.
                out = AssessmentOutput(
                    maturity_level=0, confidence=1.0,
                    rationale_ar="لا توجد مقتطفات ذات صلة في وثائق الجهة لهذه المواصفة.",
                    citations=[], gaps_ar="مطلوب رفع وثائق تخص هذه المواصفة.",
                    needs_review=True,
                )
                if not dry_run:
                    await self._assessments.upsert(
                        tenant_id=cycle.tenant_id, specification_id=spec.id,
                        cycle_id=cycle.id, output=out,
                        prompt_metadata={"reason": "no_evidence", "model": self.model},
                    )
                return SpecResult(
                    spec_id=spec.id, spec_code=spec.code,
                    status="skipped_no_evidence", output=out,
                    retrieved_chunks=0,
                    latency_ms=int((time.time() - t0) * 1000),
                )

            output, prompt_meta = await self._call_llm(spec, chunks)
            output = self._validate_citations(output, chunks)

            if not dry_run:
                await self._assessments.upsert(
                    tenant_id=cycle.tenant_id, specification_id=spec.id,
                    cycle_id=cycle.id, output=output,
                    prompt_metadata=prompt_meta,
                )
            return SpecResult(
                spec_id=spec.id, spec_code=spec.code, status="ok", output=output,
                retrieved_chunks=len(chunks),
                latency_ms=int((time.time() - t0) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 — keep batch going
            logger.exception("Spec %s failed during assessment", spec.code)
            return SpecResult(
                spec_id=spec.id, spec_code=spec.code, status="error",
                error=f"{type(exc).__name__}: {exc}",
                latency_ms=int((time.time() - t0) * 1000),
            )

    # ---- retrieval ------------------------------------------------------

    async def _retrieve_chunks(
        self, spec: SpecificationRow, tenant_id: int,
    ) -> list[dict[str, Any]]:
        query_text = build_retrieval_query(
            search_query=spec.search_query,
            name_ar=spec.name_ar,
            description_ar=spec.description_ar,
        )
        # fastembed is sync; offload.
        emb = await asyncio.to_thread(self._embedder.embed_query, query_text)
        return await self._qdrant.hybrid_search_chunks(
            tenant_id=tenant_id,
            query_dense=emb.dense,
            query_sparse_indices=emb.sparse.indices,
            query_sparse_values=emb.sparse.values,
            k=self.top_k,
        )

    # ---- Claude call ----------------------------------------------------

    async def _call_llm(
        self, spec: SpecificationRow, chunks: list[dict[str, Any]],
    ) -> tuple[AssessmentOutput, dict[str, Any]]:
        """One OpenAI Chat Completions call with strict structured-output."""
        user_prompt = build_user_prompt(
            spec_code=spec.code,
            spec_name_ar=spec.name_ar,
            spec_description_ar=spec.description_ar,
            priority=spec.priority,
            nca_conditional=spec.nca_conditional,
            acceptance_criteria=spec.acceptance_criteria,
            maturity_levels=spec.maturity_levels,
            required_elements=spec.required_elements,
            chunks=chunks,
        )

        response = await self._client.chat.completions.create(
            model=self.model,
            max_completion_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_AR},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": ASSESSMENT_JSON_SCHEMA,
            },
            temperature=0,
        )

        choice = response.choices[0]
        if choice.finish_reason not in ("stop", "length"):
            raise RuntimeError(
                f"LLM did not finish cleanly for spec {spec.code}; "
                f"finish_reason={choice.finish_reason}"
            )
        raw = choice.message.content
        if not raw:
            raise RuntimeError(
                f"LLM returned empty content for spec {spec.code} "
                f"(finish_reason={choice.finish_reason})"
            )
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"LLM JSON parse failed for spec {spec.code}: {exc}; raw={raw[:200]!r}"
            ) from exc

        output = AssessmentOutput.from_json_object(obj)
        usage = response.usage
        prompt_meta = {
            "model": self.model,
            "finish_reason": choice.finish_reason,
            "input_tokens": getattr(usage, "prompt_tokens", None),
            "output_tokens": getattr(usage, "completion_tokens", None),
            "chunk_ids_provided": [c.get("id") for c in chunks],
        }
        return output, prompt_meta

    # ---- citation validation -------------------------------------------

    @staticmethod
    def _validate_citations(
        output: AssessmentOutput, chunks: list[dict[str, Any]],
    ) -> AssessmentOutput:
        """Drop any citation whose chunk_id wasn't in the evidence shown.

        Claude is *instructed* not to fabricate ids, but we enforce it
        defensively — fabricated citations would break the Phase-4 UI.
        """
        valid_ids = {str(c.get("id")) for c in chunks}
        kept = [c for c in output.citations if c.chunk_id in valid_ids]
        if len(kept) != len(output.citations):
            logger.warning(
                "Dropped %d hallucinated citation(s) for spec verdict",
                len(output.citations) - len(kept),
            )
        output.citations = kept
        return output


def get_assessment_engine() -> AssessmentEngine:
    """FastAPI Depends factory — fresh engine per request (cheap)."""
    return AssessmentEngine()
