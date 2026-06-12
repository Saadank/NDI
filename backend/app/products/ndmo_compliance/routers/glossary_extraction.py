"""DB-extraction endpoints for the Business Glossary (BRD §6.4 / WF-05).

Mounted under ``/api/v1/products/ndmo-compliance/glossary``.  Reads source-DB
*metadata only* and turns columns into reviewable candidate terms.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.services.glossary_extraction_service import (
    GlossaryExtractionService,
    get_glossary_extraction_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary/extraction", tags=["ndmo-glossary-extraction"])


# ---------- shapes -------------------------------------------------------


class ScanBody(BaseModel):
    connection_id: UUID
    ai_draft: bool = True


class ScanResult(BaseModel):
    created: int
    skipped_existing: int
    ai_drafting: bool
    tables_scanned: int


class DraftStatus(BaseModel):
    total: int
    drafted: int
    remaining: int
    active: bool
    llm_available: bool


class AssignBody(BaseModel):
    domain_id: UUID | None = None
    user_id: int | None = None


class AcceptBody(BaseModel):
    domain_id: UUID | None = None
    force: bool = False


class DismissBody(BaseModel):
    reason: str | None = None


class ClearBody(BaseModel):
    table: str | None = None


class ClearResult(BaseModel):
    cleared: int


class ConnectionResponse(BaseModel):
    id: str
    db_type: str
    host: str
    database: str | None = None
    description: str | None = None
    status: str | None = None


class CandidateResponse(BaseModel):
    id: str
    connection_id: str | None
    schema_name: str | None
    table_name: str | None
    column_name: str | None
    inferred_name_en: str
    ai_draft_definition: str | None
    status: str
    assigned_domain_id: str | None
    assigned_to_user_id: int | None
    promoted_term_id: str | None


def _candidate_to_response(r: dict) -> CandidateResponse:
    return CandidateResponse(
        id=str(r["id"]),
        connection_id=str(r["connection_id"]) if r.get("connection_id") else None,
        schema_name=r.get("schema_name"),
        table_name=r.get("table_name"),
        column_name=r.get("column_name"),
        inferred_name_en=r["inferred_name_en"],
        ai_draft_definition=r.get("ai_draft_definition"),
        status=r["status"],
        assigned_domain_id=str(r["assigned_domain_id"]) if r.get("assigned_domain_id") else None,
        assigned_to_user_id=r.get("assigned_to_user_id"),
        promoted_term_id=str(r["promoted_term_id"]) if r.get("promoted_term_id") else None,
    )


# ---------- routes -------------------------------------------------------


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    rows = await service.list_connections(auth_user=auth_user)
    return [
        ConnectionResponse(
            id=str(r["id"]), db_type=r["db_type"], host=r["host"],
            database=r.get("database"), description=r.get("description"),
            status=r.get("status"),
        )
        for r in rows
    ]


@router.post("/scan", response_model=ScanResult)
async def scan(
    body: ScanBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    result = await service.scan(
        auth_user=auth_user, connection_id=body.connection_id, ai_draft=body.ai_draft
    )
    return ScanResult(**result)


@router.get("/draft/status", response_model=DraftStatus)
async def draft_status(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    return DraftStatus(**await service.drafting_status(auth_user=auth_user))


@router.post("/draft", response_model=DraftStatus)
async def start_drafting(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    """Resume/begin AI drafting for all still-undrafted pending candidates."""
    return DraftStatus(**await service.start_drafting(auth_user=auth_user))


@router.get("/candidates", response_model=list[CandidateResponse])
async def list_candidates(
    status: str | None = Query(default="pending"),
    schema: str | None = Query(default=None),
    table: str | None = Query(default=None),
    domain_id: UUID | None = Query(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    rows = await service.list_candidates(
        auth_user=auth_user, status=status, schema=schema, table=table, domain_id=domain_id
    )
    return [_candidate_to_response(r) for r in rows]


@router.post("/candidates/clear", response_model=ClearResult)
async def clear_candidates(
    body: ClearBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    """Bulk-dismiss all pending candidates (optionally just one table)."""
    return ClearResult(cleared=await service.clear_pending(auth_user=auth_user, table=body.table))


@router.post("/candidates/{candidate_id}/accept")
async def accept_candidate(
    candidate_id: UUID,
    body: AcceptBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    return await service.accept(
        auth_user=auth_user, candidate_id=candidate_id,
        domain_id=body.domain_id, force=body.force,
    )


@router.put("/candidates/{candidate_id}/assign", response_model=CandidateResponse)
async def assign_candidate(
    candidate_id: UUID,
    body: AssignBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    row = await service.assign(
        auth_user=auth_user, candidate_id=candidate_id,
        domain_id=body.domain_id, user_id=body.user_id,
    )
    return _candidate_to_response(row)


@router.post("/candidates/{candidate_id}/dismiss", status_code=204)
async def dismiss_candidate(
    candidate_id: UUID,
    body: DismissBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryExtractionService = Depends(get_glossary_extraction_service),
):
    await service.dismiss(
        auth_user=auth_user, candidate_id=candidate_id, reason=body.reason
    )
