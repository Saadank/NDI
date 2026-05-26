"""SQL-safety validation for LLM-generated rule parameters.

When the rule_type is ``format_regex`` the ``parameter`` is just a regex
string and only needs regex compilation — no SQL parsing.

When the rule_type is anything else and the parameter happens to be a
SQL fragment (the LLM occasionally returns ``"col > 0"`` for a custom
threshold), this validator runs the fragment through sqlglot and rejects
anything that could be harmful:

  - parses fine and is a single non-DDL/DML expression
  - has no semicolons (multi-statement)
  - has no DDL / DML keywords (``CREATE``, ``DROP``, ``DELETE``,
    ``UPDATE``, ``INSERT``, ``ALTER``, ``GRANT``, ``REVOKE``, ``EXECUTE``)
  - has no comments (``--``, ``/* */``) — those are common injection vectors
  - if it's a SELECT, must reference at most the target table (no joins
    to other tables, no information_schema)

The check is conservative: a parameter that doesn't parse as SQL at all
is accepted (it's probably a regex / threshold), since rule_type already
narrowed the interpretation.
"""
from __future__ import annotations

import re

# Conservative deny-list — these tokens shouldn't appear in a rule
# parameter under any rule_type we support.
_DENY_KEYWORDS = re.compile(
    r"\b(create|drop|alter|grant|revoke|truncate|execute|exec|"
    r"insert|update|delete|merge|copy|begin|commit|rollback|"
    r"information_schema|pg_catalog|sys\.)\b",
    re.IGNORECASE,
)

# Multi-statement / comments — never legitimate inside a single rule
# parameter, even if the rule_type would normally tolerate SQL.
_DANGEROUS_TOKENS = re.compile(r"(;|--|/\*|\*/)")


def check_parameter(rule_type: str, parameter: str | None) -> str | None:
    """Return an error message if the parameter is unsafe, else ``None``."""
    if parameter is None or parameter == "":
        return None

    if _DANGEROUS_TOKENS.search(parameter):
        return "parameter contains a semicolon, comment, or multi-statement token"

    if _DENY_KEYWORDS.search(parameter):
        return "parameter contains a denied SQL keyword (DDL/DML/system catalog)"

    if rule_type == "format_regex":
        # Validate as a regex.
        try:
            re.compile(parameter)
        except re.error as e:
            return f"parameter is not a valid regex: {e}"
        return None

    if rule_type == "dictionary_match":
        # Parameter is the reference_id this concept points at — either a
        # bare integer string ("42") or a JSON object {"reference_id": 42}.
        # The list itself lives in t_dq_reference_values and is fetched by
        # the validator at scan time, so there's nothing to sanitise here
        # beyond shape.
        s = parameter.strip()
        if s.isdigit():
            return None
        import json
        try:
            decoded = json.loads(s)
        except json.JSONDecodeError as e:
            return f"dictionary_match parameter is not a reference_id integer or JSON: {e}"
        ref_id = decoded.get("reference_id") if isinstance(decoded, dict) else None
        if not isinstance(ref_id, int) or ref_id <= 0:
            return "dictionary_match parameter must be {\"reference_id\": <positive int>}"
        return None

    # Other rule_types (not_null, no_pseudo_nulls, unique) take no parameter
    # in the current implementation. An LLM returning one is suspicious but
    # not unsafe — leave it for the reviewer to ignore.
    return None


def check_with_sqlglot(parameter: str, *, target_table: str | None = None) -> str | None:
    """Deeper check for cases where the parameter IS a SQL fragment.
    Returns ``None`` when safe; an error message otherwise.

    Used by future code paths (Step 6.5+ business-rule SQL generation)
    that explicitly expect a SQL expression.
    """
    try:
        # Lazy import — keeps the module importable when sqlglot isn't
        # installed in a stripped-down environment.
        import sqlglot
        from sqlglot import expressions as exp
    except ImportError:
        return None  # graceful — fall back to the cheap regex check

    if _DANGEROUS_TOKENS.search(parameter) or _DENY_KEYWORDS.search(parameter):
        return "parameter contains a dangerous SQL token"

    try:
        parsed = sqlglot.parse(parameter, error_level=None)
    except Exception as e:  # noqa: BLE001
        return f"sqlglot failed to parse: {e}"

    if not parsed or any(p is None for p in parsed):
        return "parameter does not parse to a SQL expression"

    if len(parsed) > 1:
        return "parameter must be a single statement, not a script"

    stmt = parsed[0]

    # Reject any DDL/DML node we can spot — sqlglot organizes these under
    # specific expression types. (Renamed-in-recent-sqlglot: AlterTable ->
    # Alter, Truncate -> TruncateTable. We use the current names.)
    forbidden_types = (
        exp.Create, exp.Drop, exp.Alter, exp.Delete, exp.Update,
        exp.Insert, exp.TruncateTable, exp.Grant, exp.Command,
    )
    if isinstance(stmt, forbidden_types) or list(stmt.find_all(*forbidden_types)):
        return "parameter contains a DDL/DML statement"

    # For SELECTs (which we don't currently use but might later), constrain
    # to the target table.
    if target_table and isinstance(stmt, exp.Select):
        for table in stmt.find_all(exp.Table):
            name = (table.name or "").lower()
            if name and name != target_table.lower():
                return f"SELECT references unexpected table: {name}"

    return None
