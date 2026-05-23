"""Regex-draft prompt — Edit-with-AI for an existing concept.

The user opens an existing format_regex concept's Edit modal, clicks
"Ask AI", and describes what should match in natural language. The LLM
returns just a regex pattern + a one-line explanation + a handful of
pass/fail example values. The user reviews in the modal's live tester
and clicks "Use this" to fill the field.

Audited via ``t_dq_llm_calls`` like every other LLM purpose.
"""
from __future__ import annotations

PROMPT_VERSION = 1


SYSTEM_PROMPT = """\
You are a regex generator for data-quality validation. The user describes \
what kind of value a column should hold; you return a single JSON object \
with a Python-compatible regular expression and a few example values.

Rules for the regex:
- Anchor with ^...$ unless the user explicitly asks for a partial match.
- Prefer tight, conservative patterns over loose ones. False positives are \
worse than false negatives here — when in doubt, narrow the pattern.
- Use plain character classes ([0-9], [A-Z]) over Unicode/locale shortcuts.
- Do NOT use Python-only constructs (named groups (?P<...>), possessive \
quantifiers, atomic groups). The pattern is also tested in JavaScript.
- Keep the pattern under 500 characters.
- NEVER produce catastrophic patterns like `.*` alone, `(a+)+`, or \
unbounded nested quantifiers.

Output JSON only, with this exact shape:
{
  "pattern": "<the regex, raw — do NOT wrap in slashes or quotes>",
  "explanation": "<one short sentence in plain English describing what matches>",
  "examples_pass": ["<sample that matches>", "<another>", ...],
  "examples_fail": ["<sample that does NOT match>", "<another>", ...],
  "confidence": "HIGH|MEDIUM|LOW"
}

Provide 2-4 examples for each of examples_pass and examples_fail. Use realistic \
values, including locale-specific ones (Arabic text, Saudi phone numbers, etc.) \
when the user mentions a locale.

Return JSON only. No commentary, no markdown, no code fences.
"""


def system_prompt() -> str:
    return SYSTEM_PROMPT


def user_prompt(nl_text: str, concept_name: str | None = None,
                current_pattern: str | None = None) -> str:
    parts = []
    if concept_name:
        parts.append(f"Concept: {concept_name}")
    if current_pattern:
        parts.append(f"Current pattern (for context — feel free to replace): {current_pattern}")
    parts.append(f"User description: {nl_text.strip()}")
    parts.append("Generate the regex and return JSON only.")
    return "\n".join(parts)
