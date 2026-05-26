"""Document-management endpoints for NDMO Compliance.

Mounted under ``/api/v1/products/ndmo-compliance/documents`` (see main.py).
Every route is gated by ``require_ndmo_compliance`` at the parent prefix,
which 403s if the tenant doesn't have the product enabled.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.services.document_service import (
    DocumentService,
    get_document_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/documents", tags=["ndmo-documents"])


# ---------- request / response shapes ------------------------------------


class InitiateUploadBody(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=512)
    mime_type: str = Field(..., min_length=1, max_length=100)
    size_bytes: int = Field(..., gt=0, le=1024 * 1024 * 1024)   # 1 GB cap
    cycle_id: int | None = Field(default=None, ge=1)


class InitiateUploadResponse(BaseModel):
    document_id: str
    minio_key: str
    presigned_put_url: str
    expires_seconds: int


class DocumentResponse(BaseModel):
    id: str
    file_name: str
    mime_type: str | None
    size_bytes: int | None
    status: str
    page_count: int | None
    cycle_id: int | None
    uploaded_at: str
    processed_at: str | None


# ---------- routes -------------------------------------------------------


@router.post("/initiate", response_model=InitiateUploadResponse)
async def initiate_upload(
    body: InitiateUploadBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Create the document row and return a presigned MinIO PUT URL.

    Client then PUTs the file bytes directly to MinIO.  The bucket-notify
    webhook will trigger the Restate ingestion workflow on PUT-complete.
    """
    result = await service.initiate_upload(
        file_name=body.file_name,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        cycle_id=body.cycle_id,
        auth_user=auth_user,
    )
    return InitiateUploadResponse(**result.__dict__)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    cycle_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    auth_user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    docs = await service.list_documents(
        auth_user=auth_user, cycle_id=cycle_id, limit=limit, offset=offset
    )
    return [_to_response(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    doc = await service.get_document(document_id=document_id, auth_user=auth_user)
    return _to_response(doc)


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
):
    """Returns the tree-shaped pipeline status from Restate.

    Shape (mirrors cortex):
      { name: "Upload", status: "succeeded", children: [
        { name: "Scan",  status: "succeeded", children: [
          { name: "Store", status: "succeeded", children: [
            { name: "Extract", status: "in_progress", children: [
              { name: "Embed", status: "pending", children: [] }
            ]}
          ]}
        ]}
      ]}
    """
    return await service.get_workflow_status(
        document_id=document_id, auth_user=auth_user
    )


def _to_response(d) -> DocumentResponse:
    return DocumentResponse(
        id=str(d.id),
        file_name=d.file_name,
        mime_type=d.mime_type,
        size_bytes=d.size_bytes,
        status=str(d.status),
        page_count=d.page_count,
        cycle_id=d.cycle_id,
        uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else "",
        processed_at=d.processed_at.isoformat() if d.processed_at else None,
    )
