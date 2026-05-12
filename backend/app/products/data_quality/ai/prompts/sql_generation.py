"""sql_generation prompt — generate a rule parameter from rule-type +
column context.

Step 6 introduces this for two paths:
  - Step 6.5: Table 13 (column rules) rows where ``parameter`` is blank
    and ``rule_type`` needs a generated value (today: format_regex —
    other rule types take literal floats or no parameter at all).
  - Step 6.6 (later): Table 12 (business rules) — full rule_type +
    parameter generation from NL.

For 6.5 the LLM only generates the parameter; the rule_type is supplied
by the user, so the response is constrained. The schema is more
permissive (``rule_type | null``) to share the prompt with 6.6.
"""
from __future__ import annotations

PROMPT_VERSION = 1


SYSTEM_PROMPT = """\
You are a data-quality rule parameter generator. Given a column name \
(optionally with a table name and rule type), return a JSON object \
describing the parameter the deterministic rule engine should use.

Supported rule types:
  not_null         — no parameter. Use null.
  max_null_rate    — float in [0, 1]. Use the user's threshold if \
provided, else 0.05 unless context strongly suggests otherwise.
  no_pseudo_nulls  — no parameter. Use null.
  unique           — no parameter. Use null.
  format_regex     — a regex string. Anchor with ^...$. Escape literal \
characters. Examples:
                       email   -> ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$
                       Saudi ID -> ^[12][0-9]{9}$
                       ISO date -> ^[0-9]{4}-[0-9]{2}-[0-9]{2}$

Rules:
- Return JSON only. No commentary, no markdown fences.
- Be conservative: when the column purpose is ambiguous, return \
``rule_type: null`` and explain in ``error_reason``.
- For format_regex, do NOT include SQL fragments, semicolons, comments, \
or anything other than a regex pattern.
- ``confidence``: HIGH only when the regex unambiguously fits common \
real-world data; MEDIUM when reasonable but tenant-specific; LOW when \
you're guessing.

Return JSON with this exact shape:
{
  "rule_type": "format_regex|not_null|max_null_rate|no_pseudo_nulls|unique" | null,
  "parameter": "<value>" or null,
  "confidence": "HIGH|MEDIUM|LOW" or null,
  "reasoning": "<one short sentence>",
  "error_reason": "<reason>" or null
}
"""


def system_prompt() -> str:
    return SYSTEM_PROMPT


def user_prompt(
    *, column_name: str, table_name: str | None,
    rule_type: str | None, dimension: str | None,
    user_hint: str | None = None,
) -> str:
    parts = [f"Column: {column_name}"]
    if table_name:
        parts.append(f"Table: {table_name}")
    if rule_type:
        parts.append(f"Rule type (fixed): {rule_type}")
    if dimension:
        parts.append(f"Dimension: {dimension}")
    if user_hint:
        parts.append(f"User hint: {user_hint}")
    parts.append("Generate the rule parameter and return JSON only.")
    return "\n".join(parts)
