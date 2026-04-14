from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.file_service import FileService, get_file_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/files", tags=["files"])


class InitiateUploadBody(BaseModel):
    request_id: UUID
    filename: str
    size: int
    mime_type: str | None = None
    sha256_hash: str


@router.post("/initiate")
async def initiate_upload(
    body: InitiateUploadBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    return await service.initiate_upload(
        request_id=body.request_id, filename=body.filename, size=body.size,
        mime_type=body.mime_type, sha256_hash=body.sha256_hash, auth_user=auth_user,
    )


@router.get("/by-request/{request_id}")
async def list_files_by_request(
    request_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    return await service.list_by_request(request_id, auth_user)


@router.put("/{file_id}/upload")
async def upload_file(
    file_id: UUID,
    file: UploadFile = File(...),
    sha256_hash: str = "",
    auth_user: AuthUser = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    data = await file.read()
    return await service.complete_upload(file_id, data, sha256_hash, auth_user)


@router.get("/{file_id}/download-url")
async def get_download_url(
    file_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    url = await service.get_download_url(file_id, auth_user)
    return {"download_url": url}


@router.delete("/{file_id}")
async def delete_file(
    file_id: UUID,
    reason: str = "manual",
    auth_user: AuthUser = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
):
    await service.delete_file(file_id, reason, auth_user)
    return {"detail": "File deleted"}
