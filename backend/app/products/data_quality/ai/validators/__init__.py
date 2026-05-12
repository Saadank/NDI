"""Per-purpose validators for LLM responses.

Every LLM response passes through (in order):
  1. ``response_schema``    — pydantic shape check for the purpose
  2. ``rule_type_whitelist`` — only the 5 supported rule_types accepted
  3. ``sql_safety``         — for parameters that are SQL/regex fragments

A failure at any layer maps to ``proposal.status='rejected_by_validator'``
with ``error_reason`` populated, so the reviewer sees the failure even
though they can't approve the proposal.
"""
