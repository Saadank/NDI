"""Stage 3: extract page-level text.

PORTED FROM:
  cortex-backend-main/tasks/content_extraction_task.py

PORTING DIFF:
  cortex                                          -> NDMO
  ───────────────────────────────────────────     ──────────────────────────
  content_miner.Miner                              app.products.ndmo_compliance
                                                     .extraction.extract_document
                                                   (our self-contained port,
                                                    no submodule)
  content_miner.TextContent                        app.products.ndmo_compliance
                                                     .extraction.PageText
                                                   (same idea — one record
                                                    per page with page_number
                                                    in metadata)
  ContentListSerde(TextContent) for restate IO     plain dict serde (Restate
                                                   handles JSON-serializable
                                                   payloads natively; we
                                                   convert PageText to dict
                                                   at the workflow boundary)
  "uploads" bucket                                 BUCKET_CLEAN (NDMO's single
                                                   canonical bucket)
  per-image page_number override                   not needed (NDMO scope is
                                                   PDF / Office; no images)
"""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from restate import RunOptions, WorkflowSharedContext
from restate.serde import BytesSerde

from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.products.ndmo_compliance.extraction import extract_document
from app.products.ndmo_compliance.gateways.object_store_gateway import (
    BUCKET_CLEAN,
    NdmoObjectStoreGateway,
)
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.products.ndmo_compliance.workflows.restate_workflows import (
    ndmo_document_ingestion_workflow,
)

logger = logging.getLogger(__name__)


@ndmo_document_ingestion_workflow.handler("Extract")
async def extract_content_task(ctx: WorkflowSharedContext, data: dict) -> list[dict]:
    """Return a list of ``{text, page_number, source_file, metadata}`` dicts.

    The next stage (Embed) consumes this directly; we use plain dicts
    instead of dataclasses across the workflow boundary so Restate's
    default JSON serde works without custom configuration.
    """
    canonical_key: str = data["object_name"]
    document_id = data["document_id"]
    tenant_id: int = data["tenant_id"]
    current_tenant_id.set(tenant_id)

    documents = DocumentRepository()
    document = await ctx.run_typed(
        "fetch document row",
        documents.find_by_id,
        document_id=document_id, tenant_id=tenant_id,
    )

    storage = NdmoObjectStoreGateway()
    file_bytes = await ctx.run_typed(
        "download canonical bytes",
        lambda: storage.get_object_bytes(bucket=BUCKET_CLEAN, key=canonical_key),
        RunOptions(serde=BytesSerde()),
    )

    # Our extract_document accepts a Path; write to a tempfile so PyMuPDF
    # / PaddleOCR can mmap it without us re-implementing a bytes-stream path.
    def _run_extractor() -> list[dict]:
        # The canonical key is "{tenant_id}/{document_id}/final.<ext>".
        ext = Path(canonical_key).suffix.lower() or ".pdf"
        with NamedTemporaryFile(suffix=ext, delete=True) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            pages = extract_document(Path(tmp.name))
        return [
            {
                "text": p.text,
                "page_number": p.page_number,
                "source_file": document.file_name,    # human-friendly name
                "metadata": dict(p.metadata or {}),
            }
            for p in pages
        ]

    pages = await ctx.run_typed("extract pages", _run_extractor)

    await ctx.run_typed(
        "update document after extraction",
        documents.update_after_extraction,
        document_id=document_id, tenant_id=tenant_id,
        page_count=len(pages), sha256=document.sha256,
    )
    await ctx.run_typed(
        "mark extracting",
        documents.update_status,
        document_id=document_id, tenant_id=tenant_id, status=DocumentStatus.EXTRACTING,
    )

    logger.info("Extracted %d pages from document %s (tenant %d)",
                len(pages), document_id, tenant_id)
    return pages
