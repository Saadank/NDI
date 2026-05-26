"""Stage 1: validate file structure and antivirus-scan it.

PORTED FROM:
  cortex-backend-main/tasks/validation_and_scanning_task.py

PORTING DIFF (rules applied here and to every subsequent task):

  cortex                                  -> Datarix-Mono / NDMO
  ──────────────────────────────────────  ──────────────────────────────────
  from dependencies import current_tenant_id
                                          from app.products.ndmo_compliance
                                            .dependencies import current_tenant_id
  from entities.file import File          from app.products.ndmo_compliance
                                            .entities.document import Document
  from enums.file_status import FileStatus
                                          from app.products.ndmo_compliance
                                            .enums.document_status
                                            import DocumentStatus
  from gateways.antivirus_gateway         from app.products.ndmo_compliance
    import AntivirusGateway                 .gateways.clamav_gateway
                                            import ClamAvGateway
  from gateways.object_storage_gateway    from app.products.ndmo_compliance
    import ObjectStorageGateway             .gateways.object_store_gateway
                                            import NdmoObjectStoreGateway
  from repositories.file_repository       from app.products.ndmo_compliance
    import FileRepository                   .repositories.document_repository
                                            import DocumentRepository
  from restate_workflows                   from app.products.ndmo_compliance
    import restate_file_creation_workflow    .workflows.restate_workflows
                                             import ndmo_document_ingestion_workflow
  from utils.file_validation              from app.products.ndmo_compliance
    import FileValidator                     .extraction.file_validation
                                             import FileValidator

  Bucket names:
    "unscanned"   -> "ndmo-unscanned"
    "clean"       -> "ndmo-clean"
    "infected"    -> "ndmo-infected"
    (cortex's tenant prefix was on the bucket name; ours is in the key.)

  Repository call:
    file_repository.find_by_id(id=file_id, user_id=user_id)
      -> document_repository.find_by_id(document_id=doc_id, tenant_id=tenant_id)
    (cortex tracked authorship for ACL; in NDMO we authorize via
     product_role at the router layer.)

  FileValidator API:
    cortex raised HTTPException on failure;
    ours returns a ValidationResult dataclass.  Failures fall through to
    the "infected" branch with a structured reason.
"""

from __future__ import annotations

import logging

from restate import RunOptions, WorkflowSharedContext
from restate.serde import BytesSerde

from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.products.ndmo_compliance.extraction.file_validation import FileValidator
from app.products.ndmo_compliance.gateways.clamav_gateway import ClamAvGateway
from app.products.ndmo_compliance.gateways.object_store_gateway import (
    BUCKET_CLEAN,
    BUCKET_INFECTED,
    BUCKET_UNSCANNED,
    NdmoObjectStoreGateway,
)
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.products.ndmo_compliance.workflows.restate_workflows import (
    ndmo_document_ingestion_workflow,
)

logger = logging.getLogger(__name__)


@ndmo_document_ingestion_workflow.handler("ValidateAndScan")
async def validate_and_scan_task(ctx: WorkflowSharedContext, data: dict) -> bool:
    """Validate file structure + antivirus-scan + move to the right bucket.

    Args (via ``data`` dict, populated by the webhook):
      * ``object_name``  — key in the ``ndmo-unscanned`` bucket
      * ``document_id``  — UUID of the ndmo.t_ndmo_documents row
      * ``tenant_id``    — int FK to public.t_tenants
      * ``user_id``      — int FK to public.t_users (the uploader)

    Returns True if the file passed validation and ClamAV (i.e. it's now
    in the ``ndmo-clean`` bucket and the workflow may proceed to Stage 2).
    Returns False if the file is rejected — caller should NOT continue.
    """
    object_name: str = data["object_name"]
    document_id = data["document_id"]
    tenant_id: int = data["tenant_id"]

    # Cortex pattern: pin the tenant on the ContextVar so any downstream
    # helper that reads it sees the right value.
    current_tenant_id.set(tenant_id)

    storage = NdmoObjectStoreGateway()
    antivirus = ClamAvGateway()
    documents = DocumentRepository()

    # ---- 1. Download the candidate bytes -------------------------------
    file_content: bytes = await ctx.run_typed(
        "download from unscanned",
        lambda: storage.get_object_bytes(bucket=BUCKET_UNSCANNED, key=object_name),
        RunOptions(serde=BytesSerde()),
    )

    # ---- 2. Mark "scanning" and fetch metadata --------------------------
    document = await ctx.run_typed(
        "fetch document row",
        documents.find_by_id,
        document_id=document_id, tenant_id=tenant_id,
    )
    await ctx.run_typed(
        "mark scanning",
        documents.update_status,
        document_id=document_id, tenant_id=tenant_id, status=DocumentStatus.SCANNING,
    )

    # ---- 3. Run validator + antivirus -----------------------------------
    rejection_reason: str | None = None
    validation = await ctx.run_typed(
        "validate file bytes",
        lambda: FileValidator.validate(file_content, document.extension),
    )
    if not validation.valid:
        rejection_reason = f"validation failed: {validation.error}"
    else:
        is_clean, signature = await ctx.run_typed(
            "clamav scan",
            antivirus.scan_bytes,
            data=file_content,
        )
        if not is_clean:
            rejection_reason = f"antivirus rejected: {signature}"

    # ---- 4. Route to the right state bucket -----------------------------
    target_bucket = BUCKET_INFECTED if rejection_reason else BUCKET_CLEAN
    final_status = DocumentStatus.INFECTED if rejection_reason else DocumentStatus.CLEAN

    await ctx.run_typed(
        f"copy to {target_bucket}",
        storage.copy_object,
        source_bucket=BUCKET_UNSCANNED, source_key=object_name,
        destination_bucket=target_bucket, destination_key=object_name,
    )
    await ctx.run_typed(
        "remove from unscanned",
        storage.remove_object,
        bucket=BUCKET_UNSCANNED, key=object_name,
    )
    await ctx.run_typed(
        f"update status to {final_status.value}",
        documents.update_status,
        document_id=document_id, tenant_id=tenant_id, status=final_status,
    )

    if rejection_reason:
        logger.warning("Document %s rejected (tenant %d): %s",
                       document_id, tenant_id, rejection_reason)
        return False

    logger.info("Document %s passed validation + ClamAV (tenant %d)",
                document_id, tenant_id)
    return True
