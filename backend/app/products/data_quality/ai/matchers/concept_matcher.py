"""LLM-augmented concept matcher (moved from
``services/llm_matcher.py`` in Step 6.0 — was Anthropic-only, now goes
through the provider-agnostic ``ai/client.py``).

Called by the active-rule orchestrator only for columns the fuzzy
matcher couldn't classify. Graceful degradation: when the LLM is
unreachable, returns an empty match list rather than raising — the scan
still completes with just the fuzzy matches it already had.

Returned dicts are intentionally shape-compatible with
``services.fuzzy_matcher.match_column``: ``concept_id``, ``dimension``,
``concept``, ``matched_by``, ``confidence``, ``matcher_score``,
``matcher_reasoning``. The orchestrator merges the two lists.
"""
from __future__ import annotations

import logging

from app.products.data_quality.ai.client import get_llm_client, is_llm_available
from app.products.data_quality.ai.prompts import concept_match as prompt

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Back-compat shim — same name the old llm_matcher exposed so the
    orchestrator import didn't need a behavioural rewrite."""
    return is_llm_available()


async def match_column(
    column: dict, concepts: list[dict], *, semantic_type: str | None,
) -> list[dict]:
    """Ask the LLM which concepts match this column. Returns a list of
    fuzzy-compatible match dicts (possibly empty)."""
    client = get_llm_client()
    if client is None:
        return []

    system = prompt.system_prompt(concepts)
    user = prompt.user_prompt(column, semantic_type)

    result = await client.call(system=system, user=user, json_mode=True)
    if not result.success:
        logger.warning(
            "concept_match LLM call failed for %s: %s",
            column.get("column_name"), result.error,
        )
        return []

    parsed = result.parsed_json
    if not isinstance(parsed, dict):
        return []
    matches = parsed.get("matches")
    if not isinstance(matches, list):
        return []

    # Index the dictionary so we can ignore hallucinated concept_ids.
    by_id = {c["id"]: c for c in concepts}
    out: list[dict] = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        cid = m.get("concept_id")
        if cid not in by_id:
            continue
        conf = (m.get("confidence") or "").lower()
        if conf not in ("high", "medium", "low"):
            continue
        c = by_id[cid]
        out.append({
            "concept_id": cid,
            "dimension": c["dimension"],
            "concept": c["concept"],
            "matched_by": "llm",
            "confidence": conf,
            "matcher_score": _confidence_to_score(conf),
            "matcher_reasoning": (m.get("reasoning") or "").strip()[:500],
        })
    return out


def _confidence_to_score(conf: str) -> float:
    return {"high": 0.9, "medium": 0.65, "low": 0.4}.get(conf, 0.0)
