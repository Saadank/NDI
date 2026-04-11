from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.platform.services.authentication_service import AuthenticationService, get_authentication_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login")
async def login(body: LoginRequest, service: AuthenticationService = Depends(get_authentication_service)):
    return await service.login(body.username, body.password)


@router.post("/refresh")
async def refresh(body: RefreshRequest, service: AuthenticationService = Depends(get_authentication_service)):
    return await service.refresh(body.refresh_token)


@router.post("/logout")
async def logout(body: RefreshRequest, service: AuthenticationService = Depends(get_authentication_service)):
    result = await service.logout(body.refresh_token)
    return {"success": result}
