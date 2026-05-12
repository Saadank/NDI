"""Belt-and-suspenders check that an LLM-proposed ``rule_type`` is one of
the five rule types the deterministic validator actually implements.

Without this, a hallucinated rule_type (e.g. ``"range_check"``) could
sneak through the schema layer (Literal types catch most of it) but a
hand-rolled service path that consumed the raw LLM dict directly would
miss it. This module is the single source of truth for the whitelist
across server-side code.
"""
from __future__ import annotations

# Mirrors Phase 1's validator. New rule types must be added here AND
# implemented in services/validator_service.py before they can ride.
RULE_TYPE_WHITELIST: frozenset[str] = frozenset({
    "not_null",
    "max_null_rate",
    "no_pseudo_nulls",
    "unique",
    "format_regex",
})


def is_allowed(rule_type: str | None) -> bool:
    return rule_type is not None and rule_type in RULE_TYPE_WHITELIST


def check(rule_type: str | None) -> str | None:
    """Returns an error message if disallowed, else ``None``."""
    if not is_allowed(rule_type):
        return (
            f"rule_type={rule_type!r} is not in the supported set "
            f"({sorted(RULE_TYPE_WHITELIST)}). Reviewer can pick a manual "
            f"rule_type instead, or the row stays as unsupported_logic."
        )
    return None
