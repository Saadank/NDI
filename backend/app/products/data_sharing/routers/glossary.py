from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.glossary_service import GlossaryService, get_glossary_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary", tags=["glossary"])


class CreateEntryBody(BaseModel):
    term: str
    definition: str | None = None
    category: str | None = None
    connection_id: UUID | None = None


@router.get("/")
async def list_entries(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryService = Depends(get_glossary_service),
):
    return await service.list_entries(auth_user.tenant_id)


@router.post("/")
async def create_entry(
    body: CreateEntryBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryService = Depends(get_glossary_service),
):
    return await service.create_entry(
        auth_user.tenant_id, body.term, body.definition, body.category,
        body.connection_id, auth_user.user_id,
    )


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryService = Depends(get_glossary_service),
):
    await service.delete_entry(entry_id, auth_user.tenant_id)
    return {"detail": "Entry deleted"}
