"""Restate workflow declaration.

Mirrors cortex's top-level ``restate_workflows.py``.  One workflow object
shared by every stage handler.  The handlers live in ``tasks/*.py`` and
register themselves via ``@ndmo_document_ingestion_workflow.handler(...)``.
"""

from __future__ import annotations

from restate import Workflow

ndmo_document_ingestion_workflow = Workflow("NdmoDocumentIngestionWorkflow")
