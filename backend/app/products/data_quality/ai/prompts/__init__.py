"""Prompt modules for the Data Quality LLM purposes.

Each module exposes:

- a versioned ``PROMPT_VERSION`` (int) so the audit table can identify
  which prompt produced a given LLM call;
- a ``system_prompt()`` function (or constant) that renders the system
  message;
- a ``user_prompt(...)`` function that renders the per-call user message;
- per-purpose validators imported from ``ai/validators/``.

Prompts never reference raw row values from the source. Any column-name
or pattern-signature input must already have passed through the PII
anonymizer; raw values are stripped at the gateway.
"""
