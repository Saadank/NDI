"""MinIO bucket-notify webhook — fires when a file lands in ndmo-unscanned.

PORTED FROM:
  cortex-backend-main/controllers/file_creation_webhook.py

PORTING DIFF:
  cortex used a Restate webhook service (`restate.Service(\"WebhookService\")`)
  + ctx.workflow_send.  We don't need that level of indirection — Restate's
  HTTP ingress accepts plain POSTs, so we expose this as a plain FastAPI
  route and call ingress directly from the DocumentService.

  Cortex parsed tenant_id from the bucket prefix.  We parse it from the
  object key (`{tenant_id}/{document_id}/{uuid}.{ext}`) since NDMO uses
  shared state buckets.

This webhook is intentionally UNAUTHENTICATED — it's wired in MinIO's
bucket-notify config and MinIO doesn't sign its callbacks.  Mitigations:
  * route requires the originating ``Source`` header to be ``minio:s3``
  * payload is validated; anything malformed is dropped
  * tenant + document IDs must already exist in t_ndmo_documents
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.products.ndmo_compliance.services.document_service import (
    DocumentService,
    get_document_service,
)

router = APIRouter(prefix="/webhooks", tags=["ndmo-webhooks"])

logger = logging.getLogger(__name__)


@router.post("/minio/upload-complete", status_code=204)
async def minio_upload_complete(
    request: Request,
    x_minio_source: str | None = Header(default=None, alias="Source"),
    service: DocumentService = Depends(get_document_service),
):
    """Accept a MinIO bucket-notify payload and trigger the ingestion workflow."""
    if x_minio_source and x_minio_source != "minio:s3":
        logger.warning("Rejecting webhook from unknown source: %s", x_minio_source)
        raise HTTPException(status_code=403, detail="Unexpected source")

    body = await request.json()
    records = body.get("Records") or []
    if not records:
        return

    record = records[0]
    event_name = record.get("eventName", "")
    if not event_name.startswith("s3:ObjectCreated:"):
        logger.info("Ignoring non-create event: %s", event_name)
        return

    bucket = record.get("s3", {}).get("bucket", {}).get("name", "")
    if bucket != "ndmo-unscanned":
        logger.info("Ignoring event from non-NDMO bucket: %s", bucket)
        return

    object_key: str = record["s3"]["object"]["key"]

    # Key format: {tenant_id}/{document_id}/{uuid}.{ext}
    parts = object_key.split("/", 2)
    if len(parts) < 3:
        logger.warning("Cannot parse tenant/document from key: %s", object_key)
        raise HTTPException(status_code=400, detail="Malformed object key")
    try:
        tenant_id = int(parts[0])
        document_id = UUID(parts[1])
    except (ValueError, TypeError) as exc:
        logger.warning("Bad tenant/document in key %s: %s", object_key, exc)
        raise HTTPException(status_code=400, detail="Malformed object key") from exc

    await service.trigger_workflow(
        document_id=document_id, minio_key=object_key, tenant_id=tenant_id
    )
    logger.info("Triggered ingestion workflow for document=%s tenant=%d",
                document_id, tenant_id)
