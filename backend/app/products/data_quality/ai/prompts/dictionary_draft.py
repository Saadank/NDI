"""Dictionary-draft prompt — Edit-with-AI for a dictionary_match concept.

The user opens a dictionary_match concept's Edit modal, clicks "Ask AI to
draft values", and describes what set of values is allowed (e.g. "GCC
country codes", "Saudi commercial banks", "ISO 4217 currency codes"). The
LLM returns a concrete list of allowed values plus a short explanation.
The user reviews and edits before saving — they are the reviewer.

Audited via ``t_dq_llm_calls`` like every other LLM purpose.
"""
from __future__ import annotations

PROMPT_VERSION = 1


SYSTEM_PROMPT = """\
You are a dictionary generator for data-quality validation. The user \
describes a set of allowed values a column should hold; you return a \
single JSON object listing those values and a short explanation.

Rules for the values list:
- Return the canonical, real-world entries — not invented placeholders.
- Use the natural form a database column would carry. ISO 4217 codes are \
three uppercase letters (USD, EUR, SAR). Country codes default to ISO \
3166-1 alpha-2 (SA, AE, KW) unless the user asks otherwise. Bank names \
should be the legal short name in the language the user requested.
- Deduplicate. Strip surrounding whitespace.
- Cap at 200 values. If the real-world list is larger, return the most \
common subset and say so in the explanation.
- When you can't enumerate the set with reasonable confidence (e.g. \
"all valid email addresses"), set confidence=LOW and put a brief reason \
in the explanation — the user can decide whether to use it.

Match behaviour:
- ``case_sensitive=false`` is the default — pick TRUE only when the spec \
genuinely cares (e.g. ISO 4217 mandates uppercase). Most lists (city \
names, bank names) should stay case-insensitive so "Riyadh" and "riyadh" \
both validate.

Output JSON only, with this exact shape:
{
  "values": ["<value1>", "<value2>", ...],
  "case_sensitive": true|false,
  "explanation": "<one short sentence in plain English describing the set>",
  "confidence": "HIGH|MEDIUM|LOW"
}

Return JSON only. No commentary, no markdown, no code fences.
"""


def system_prompt() -> str:
    return SYSTEM_PROMPT


def user_prompt(nl_text: str, concept_name: str | None = None,
                current_values: list[str] | None = None) -> str:
    parts = []
    if concept_name:
        parts.append(f"Concept: {concept_name}")
    if current_values:
        preview = ", ".join(current_values[:10])
        suffix = f", +{len(current_values) - 10} more" if len(current_values) > 10 else ""
        parts.append(f"Current values (for context — feel free to replace): {preview}{suffix}")
    parts.append(f"User description: {nl_text.strip()}")
    parts.append("Generate the values list and return JSON only.")
    return "\n".join(parts)
