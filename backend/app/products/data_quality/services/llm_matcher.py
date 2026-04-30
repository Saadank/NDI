"""LLM-augmented concept matcher (Anthropic Haiku 4.5).

Called by the orchestrator only for columns the fuzzy matcher couldn't
classify. The dictionary goes in as a *cached* system prompt so subsequent
calls in the same scan session pay only a small read-cache fee instead of
re-billing the dictionary tokens.

Graceful degradation:
- No ANTHROPIC_API_KEY → log once, return empty matches.
- API error / parse error → log, return empty matches (don't fail the scan).
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy SDK client — avoids import cost when DQ isn't being used and skips
# initialization entirely when no key is configured.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _client():
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.warning("anthropic package not installed — LLM matcher disabled")
        return None
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


def is_available() -> bool:
    return _client() is not None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a data-quality concept matcher. Given a database column's metadata \
and a dictionary of quality concepts, decide which concepts the column \
should be subject to.

Each dictionary concept declares:
- dimension: completeness | validity | uniqueness
- concept: short stable identifier
- synonyms: column-name patterns this concept answers to
- rule_type: not_null | max_null_rate | no_pseudo_nulls | unique | format_regex
- applies_to_types: which table semantic types this concept applies on \
(empty list = applies to any semantic type)
- notes: free-form context

Confidence levels:
- HIGH: column name is a direct synonym (or near-synonym in another \
language/abbreviation), AND the profile supports the concept. Auto-applies.
- MEDIUM: column name is plausibly related (e.g. \"contact_method\" could be \
an email column) but not a clear synonym. Awaits human approval.
- LOW: weak/uncertain match worth proposing.

Rules:
- Only return concepts that match. If nothing matches, return an empty array.
- Only return concept_ids that exist in the supplied dictionary.
- Ignore concepts whose applies_to_types is non-empty and does NOT include \
the table's semantic_type.
- Be conservative — never invent concepts.
- A column may match multiple concepts (e.g. a primary identifier column \
matches both a uniqueness concept AND a completeness one).

Return JSON only, with this exact shape:
{
  \"matches\": [
    {\"concept_id\": <int>, \"confidence\": \"HIGH|MEDIUM|LOW\", \
\"reasoning\": \"<one short sentence>\"}
  ]
}
"""


def _format_concepts_for_prompt(concepts: list[dict]) -> str:
    """Compact JSON dump of the dictionary for the LLM. Stable across calls
    so prompt caching works."""
    minimal = [
        {
            "concept_id": c["id"],
            "dimension": c["dimension"],
            "concept": c["concept"],
            "synonyms": c.get("synonyms") or [],
            "rule_type": c["rule_type"],
            "applies_to_types": c.get("applies_to_types") or [],
            "notes": c.get("notes") or "",
        }
        for c in concepts if c.get("enabled", True)
    ]
    return json.dumps(minimal, ensure_ascii=False, indent=None)


def _format_column(column: dict, semantic_type: str | None) -> str:
    """Single-column user-prompt body."""
    top = (column.get("top_patterns") or [])[:3]
    top_str = ", ".join(f"{t['pattern']}({t['count']})" for t in top) or "(none)"
    return (
        f"Column: {column['column_name']}\n"
        f"Declared type: {column.get('declared_data_type') or '?'}\n"
        f"Type category: {column.get('type_category') or '?'}\n"
        f"Inferred column type: {column.get('inferred_column_type') or '?'}\n"
        f"Dominant pattern: {column.get('dominant_pattern') or '(none)'} "
        f"({_pct(column.get('pattern_conformance_rate'))})\n"
        f"Top patterns: {top_str}\n"
        f"Distinct: {column.get('distinct_count')} "
        f"(rate {_pct(column.get('distinct_rate'))})\n"
        f"Null rate: {_pct(column.get('null_rate'))}\n"
        f"\n"
        f"Table semantic type: {semantic_type or '(unset)'}\n"
        f"\n"
        f"Match this column against the dictionary above and return matches as JSON."
    )


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def match_column(
    column: dict, concepts: list[dict], *, semantic_type: str | None,
) -> list[dict]:
    """Ask the LLM which concepts match this column. Returns a list of
    {concept_id, dimension, concept, matched_by, confidence, matcher_score,
     matcher_reasoning} dicts (compatible with fuzzy_matcher output)."""
    cli = _client()
    if cli is None:
        return []

    settings = get_settings()
    concept_block = _format_concepts_for_prompt(concepts)
    user_prompt = _format_column(column, semantic_type)

    try:
        # Cache control on the dictionary block — Anthropic charges ~10% for
        # cache reads after the first call in a 5-min window. Cuts cost when
        # batching across many columns.
        resp = await cli.messages.create(
            model=settings.DQ_LLM_MODEL,
            max_tokens=settings.DQ_LLM_MAX_OUTPUT_TOKENS,
            system=[
                {"type": "text", "text": _SYSTEM_PROMPT,
                 "cache_control": {"type": "ephemeral"}},
                {"type": "text",
                 "text": f"Dictionary:\n{concept_block}",
                 "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM matcher call failed for %s: %s",
                       column.get("column_name"), e)
        return []

    text = "".join(block.text for block in resp.content if getattr(block, "text", None))
    if not text:
        return []

    parsed = _parse_response(text)
    if not parsed:
        return []

    # Index concepts for cheap lookup + filter to those the LLM actually saw.
    by_id = {c["id"]: c for c in concepts}
    out: list[dict] = []
    for m in parsed:
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


def _parse_response(text: str) -> list[dict]:
    """Pull the matches array out of the LLM response. We're permissive —
    the model sometimes wraps JSON in code fences or adds a small lead-in.
    """
    text = text.strip()
    if "```" in text:
        # Strip ```json or ``` fences regardless of language tag.
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Last-ditch: hunt for a {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            logger.warning("LLM response not parseable as JSON: %s", text[:200])
            return []
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            logger.warning("LLM JSON salvage failed: %s", text[:200])
            return []

    matches = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(matches, list):
        return []
    return [m for m in matches if isinstance(m, dict)]


def _confidence_to_score(conf: str) -> float:
    return {"high": 0.9, "medium": 0.65, "low": 0.4}.get(conf, 0.0)
