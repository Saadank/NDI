"""LLM-touching code for the Data Quality product (Step 6).

Quarantined here so the deterministic rule engine in
`data_quality/services/`, `repositories/`, and `routers/` stays auditable
on its own. Only `proposal_service.py` (when 6.7 lands) is allowed to
cross the boundary, at human-approval time.

Provider: Ollama (local). Was Anthropic in earlier iterations; the
client abstraction in `client.py` keeps the door open for future
swaps without touching prompt or service code.
"""
