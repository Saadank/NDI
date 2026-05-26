"""column_match prompt — given a business term + a table's column list,
return a **ranked list** of column-name candidates with confidence.

This is the multilingual / abbreviation-resolving step in Step 6.6's
hard path for Table 12: a row like

    rule_name="Customer email validation", logic_nl="...",
    table="customers", column=""

needs the LLM to look at the actual columns of ``customers`` and pick
which one(s) the business term ``Customer email`` is talking about
(``email`` / ``contact_email`` / ``البريد_الإلكتروني`` / ``e_mail`` / ...).

Output is always ranked + confidence-annotated. The top candidate
feeds the subsequent ``sql_generation`` call; the others are stashed
on the proposal's ``candidates`` field so the reviewer can pick a
different column at approval time.
"""
from __future__ import annotations

import json

PROMPT_VERSION = 1


SYSTEM_PROMPT = """\
You are a database column matcher. Given a business term (possibly in \
English, Arabic, mixed, or with abbreviations), find which columns in \
the supplied list the term refers to.

Each column entry declares:
- column: the column name as it exists in the database
- type: declared SQL type (e.g. varchar(255), int, timestamp)
- inferred: detected semantic kind (email, identifier, date, etc.)
- pattern: dominant value pattern when known

Confidence levels:
- HIGH: column name is a direct synonym (or near-synonym in another \
language/transliteration), AND the type/pattern fits.
- MEDIUM: plausibly related but not certain (e.g. business term \
"contact" could be email or phone).
- LOW: weak / structural / fallback match worth listing for reviewer.

Rules:
- Return ONLY columns that exist in the supplied list. Never invent.
- Column names may be in any language including Arabic; consider \
transliteration and common abbreviations (e.g. cstmr_eml = customer_email).
- Up to 5 candidates per term. Rank by descending confidence.
- If nothing plausibly matches, return an empty array — the upstream \
caller turns that into a 'reviewer needed' proposal.

Return JSON only, with this exact shape:
{
  "matches": [
    {"column_name": "<exact name from input list>",
     "confidence": "HIGH|MEDIUM|LOW",
     "reasoning": "<one short sentence>"}
  ]
}
"""


def system_prompt() -> str:
    return SYSTEM_PROMPT


def user_prompt(
    *, term: str, term_definition: str | None,
    table_name: str | None, columns: list[dict],
    glossary_hint: list[dict] | None = None,
) -> str:
    """Render the per-row user message.

    ``columns`` entries: {column_name, declared_data_type, type_category,
                          inferred_column_type, dominant_pattern}
    ``glossary_hint``: optional list of glossary entries to provide
                       additional tenant-specific context.
    """
    minimal_cols = [
        {
            "column": c.get("column_name"),
            "type": c.get("declared_data_type") or "",
            "inferred": c.get("inferred_column_type") or "",
            "pattern": (c.get("dominant_pattern") or "")[:60],
        }
        for c in columns
    ]
    parts = [
        f"Business term: {term}",
    ]
    if term_definition:
        parts.append(f"Definition: {term_definition}")
    if table_name:
        parts.append(f"Target table: {table_name}")
    if glossary_hint:
        compact = [{"term": g["term"], "synonyms": (g.get("synonyms") or [])[:5]}
                   for g in glossary_hint[:20]]
        parts.append(
            f"Tenant glossary (for context):\n{json.dumps(compact, ensure_ascii=False)}"
        )
    parts.append(
        f"Available columns:\n{json.dumps(minimal_cols, ensure_ascii=False)}"
    )
    parts.append(
        "Return the ranked column candidates as JSON only. Top match goes first."
    )
    return "\n".join(parts)
