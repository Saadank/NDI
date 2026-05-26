"""Repositories that back the LLM-touching workflows.

Live under ``ai/`` (not the top-level ``repositories/``) to keep the
import boundary clear: anything in ``services/``, ``repositories/``,
``routers/`` may NOT import these. Only ``ai/services/proposal_service``
crosses back when applying approved proposals.
"""
