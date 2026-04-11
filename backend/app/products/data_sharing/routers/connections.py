from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.connection_service import ConnectionService, get_connection_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/connections", tags=["connections"])


class CreateConnectionBody(BaseModel):
    db_type: str
    host: str
    port: int
    database: str | None = None
    username: str
    password: str
    description: str | None = None


@router.get("/")
async def list_connections(
    auth_user: AuthUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return await service.list_connections(auth_user)


@router.post("/")
async def create_connection(
    body: CreateConnectionBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return await service.create_connection(body.model_dump(), auth_user)


@router.post("/{connection_id}/test")
async def test_connection(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    return await service.test_connection(connection_id, auth_user)


@router.delete("/{connection_id}")
async def delete_connection(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConnectionService = Depends(get_connection_service),
):
    await service.delete_connection(connection_id, auth_user)
    return {"detail": "Connection deleted"}
