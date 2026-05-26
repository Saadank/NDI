"""Top-level orchestrator: chains the 4 NDMO ingestion stages.

PORTED FROM:
  cortex-backend-main/tasks/file_creation_workflow.py

PORTING DIFF:
  cortex had 8 parallel post-embedding "identification" tasks (title,
  tags, summary, classification, references, KG, template) — none of
  those apply to NDMO compliance assessment.  Dropped.

  Final pipeline: Upload → Scan → Store → Extract → Embed → Ready.
  (The Phase-3 assessment engine reads from Qdrant + Postgres; it
  doesn't run inside this workflow.)
"""

from __future__ import annotations

import logging

from restate import WorkflowContext, WorkflowSharedContext

from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.products.ndmo_compliance.workflows.restate_workflows import (
    ndmo_document_ingestion_workflow,
)
from app.products.ndmo_compliance.workflows.tasks.content_embedding_task import (
    embed_content_task,
)
from app.products.ndmo_compliance.workflows.tasks.content_extraction_task import (
    extract_content_task,
)
from app.products.ndmo_compliance.workflows.tasks.storing_task import store_task
from app.products.ndmo_compliance.workflows.tasks.validation_and_scanning_task import (
    validate_and_scan_task,
)

logger = logging.getLogger(__name__)


class _TaskState:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@ndmo_document_ingestion_workflow.main(name="NdmoDocumentIngestionWorkflow")
async def ndmo_document_ingestion(ctx: WorkflowContext, data: dict) -> None:
    """Linear chain.  Each stage updates t_ndmo_documents.status; we also
    push a tree-shaped status dict into the workflow KV so the front-end
    can poll a single endpoint for live progress.
    """
    object_name: str = data["object_name"]
    document_id: str = str(data["document_id"])
    tenant_id: int = data["tenant_id"]
    current_tenant_id.set(tenant_id)

    status = await _set_status(ctx, data={"Upload": _TaskState.SUCCEEDED,
                                          "Scan": _TaskState.IN_PROGRESS})

    # ---- Stage 1: Validate + ClamAV --------------------------------------
    safe = await ctx.workflow_call(
        validate_and_scan_task,
        key=ctx.key(),
        arg={"object_name": object_name, "document_id": document_id, "tenant_id": tenant_id},
    )
    if not safe:
        await _set_status(ctx, current_status=status,
                          data={"Scan": _TaskState.FAILED})
        await _mark_failed(document_id, tenant_id)
        return
    status = await _set_status(ctx, current_status=status,
                               data={"Scan": _TaskState.SUCCEEDED,
                                     "Store": _TaskState.IN_PROGRESS})

    # ---- Stage 2: Store (move to canonical key, convert if needed) -------
    canonical_key = await ctx.workflow_call(
        store_task,
        key=ctx.key(),
        arg={"object_name": object_name, "document_id": document_id, "tenant_id": tenant_id},
    )
    status = await _set_status(ctx, current_status=status,
                               data={"Store": _TaskState.SUCCEEDED,
                                     "Extract": _TaskState.IN_PROGRESS})

    # ---- Stage 3: Extract page-level text --------------------------------
    pages = await ctx.workflow_call(
        extract_content_task,
        key=ctx.key(),
        arg={"object_name": canonical_key, "document_id": document_id, "tenant_id": tenant_id},
    )
    if not pages:
        await _set_status(ctx, current_status=status,
                          data={"Extract": _TaskState.FAILED})
        await _mark_failed(document_id, tenant_id)
        return
    status = await _set_status(ctx, current_status=status,
                               data={"Extract": _TaskState.SUCCEEDED,
                                     "Embed": _TaskState.IN_PROGRESS})

    # ---- Stage 4: Chunk + embed + Qdrant upsert --------------------------
    result = await ctx.workflow_call(
        embed_content_task,
        key=ctx.key(),
        arg={"pages": pages, "document_id": document_id, "tenant_id": tenant_id},
    )
    status = await _set_status(ctx, current_status=status,
                               data={"Embed": _TaskState.SUCCEEDED})
    logger.info("Document %s ingested: %d chunks, status=ready",
                document_id, result.get("chunks", 0))


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------


async def _set_status(
    ctx: WorkflowContext,
    *,
    data: dict[str, str],
    current_status: dict | None = None,
) -> dict:
    new_status = dict(current_status or {})
    new_status.update(data)
    ctx.set(name="status", value=new_status)
    return new_status


async def _mark_failed(document_id: str, tenant_id: int) -> None:
    documents = DocumentRepository()
    await documents.update_status(
        document_id=document_id, tenant_id=tenant_id, status=DocumentStatus.FAILED
    )


@ndmo_document_ingestion_workflow.handler("GetStatus")
async def get_status(ctx: WorkflowSharedContext) -> dict | None:
    """Tree-shaped status for the front-end progress widget.

    Mirrors cortex's get_status but with the NDMO 5-node shape:
      Upload → Scan → Store → Extract → Embed
    """
    status = await ctx.get("status")
    if status is None:
        return None
    try:
        upload = {"name": "Upload", "status": status.get("Upload", "pending"), "children": []}
        scan = {"name": "Scan", "status": status.get("Scan", "pending"), "children": []}
        store = {"name": "Store", "status": status.get("Store", "pending"), "children": []}
        extract = {"name": "Extract", "status": status.get("Extract", "pending"), "children": []}
        embed = {"name": "Embed", "status": status.get("Embed", "pending"), "children": []}
        upload["children"].append(scan)
        scan["children"].append(store)
        store["children"].append(extract)
        extract["children"].append(embed)
        return upload
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_status build failed: %s", exc)
        return None
