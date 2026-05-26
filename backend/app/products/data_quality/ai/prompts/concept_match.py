"""Concept-match prompt — pick which dictionary concepts apply to a column.

Used by ``ai/matchers/concept_matcher.py``, which is invoked by the
deterministic active-rule applier only for columns that the fuzzy matcher
couldn't classify. The orchestrator caches the concept dictionary in
memory for the duration of a scan so this prompt is re-rendered once per
column (rather than once per column per concept).
"""
from __future__ import annotations

import json
from typing import Any

PROMPT_VERSION = 1


SYSTEM_PROMPT = """\
You are a data-quality concept matcher. Given a database column's metadata \
and a dictionary of quality concepts, decide which concepts the column \
should be subject to.

Each dictionary concept declares:
- dimension: completeness | validity | uniqueness
- concept: short stable identifier
- synonyms: column-name patterns this concept answers to
- rule_type: not_null | no_pseudo_nulls | unique | format_regex
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
- Be conservative — never invent concepts.
- A column may match multiple concepts (e.g. a primary identifier column \
matches both a uniqueness concept AND a completeness one).
- Column names may be in any language including Arabic; consider \
transliteration and common abbreviations.

Return JSON only, with this exact shape:
{
  \"matches\": [
    {\"concept_id\": <int>, \"confidence\": \"HIGH|MEDIUM|LOW\", \
\"reasoning\": \"<one short sentence>\"}
  ]
}
"""


def system_prompt(concepts: list[dict]) -> str:
    """Compose the system message: instructions + dictionary block.

    The dictionary lives in the system prompt (not the user message) so
    providers that support prompt caching can keep it warm across calls
    within a scan. Ollama doesn't cache, but the layout costs nothing
    extra and is correct for the provider abstraction."""
    return f"{SYSTEM_PROMPT}\nDictionary:\n{_format_concepts(concepts)}"


def user_prompt(column: dict, semantic_type: str | None) -> str:
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


def _format_concepts(concepts: list[dict]) -> str:
    minimal = [
        {
            "concept_id": c["id"],
            "dimension": c["dimension"],
            "concept": c["concept"],
            "synonyms": c.get("synonyms") or [],
            "rule_type": c["rule_type"],
            "notes": c.get("notes") or "",
        }
        for c in concepts if c.get("enabled", True)
    ]
    return json.dumps(minimal, ensure_ascii=False, indent=None)


def _pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(v)
