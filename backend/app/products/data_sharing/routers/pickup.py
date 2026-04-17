"""Public pickup portal router — unauthenticated.

Exposed at /api/v1/pickup/*. Validates a hashed magic-link token, records DPA
acceptance, and issues ephemeral presigned MinIO URLs for downloads. Never
uses get_current_user.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.products.data_sharing.repositories.external_recipient_repository import ExternalRecipientRepository
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.services.pickup_service import PickupService, get_pickup_service
from app.utils.exceptions import ResourceNotFoundException
from app.utils.rate_limit import pickup_limiter
from app.utils.request_info import client_ip, user_agent

router = APIRouter(prefix="/pickup", tags=["pickup"])

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _rate_limit(request: Request, token: str) -> None:
    settings = get_settings()
    key = f"{client_ip(request) or 'unknown'}:{token[:16]}"
    pickup_limiter.check(key, settings.PICKUP_RATE_LIMIT_PER_MINUTE)


async def _load_request_and_recipient(token_row: dict) -> tuple[dict, dict | None]:
    request_repo = ShareRequestRepository()
    recipients = ExternalRecipientRepository()
    request = await request_repo.find_by_id(token_row["share_request_id"], token_row["tenant_id"])
    recipient = None
    if request and request.get("external_recipient_id"):
        recipient = await recipients.find_by_id(request["external_recipient_id"], request["tenant_id"])
    return request, recipient


def _request_summary(token: dict, request: dict, recipient: dict | None) -> dict:
    return {
        "title": request.get("title"),
        "purpose": request.get("purpose"),
        "requester_org": recipient.get("org_name") if recipient else None,
        "expires_at": token["expires_at"],
        "dpa_required": True,
        "dpa_accepted": token["dpa_accepted_at"] is not None,
        "download_count": token["download_count"],
        "max_downloads": token["max_downloads"],
    }


@router.get("/{token}")
async def pickup_overview(
    token: str,
    request: Request,
    pickup: PickupService = Depends(get_pickup_service),
):
    _rate_limit(request, token)
    row = await pickup.verify_token(token)
    row = await pickup.mark_opened_if_needed(row, client_ip(request), user_agent(request))
    share_request, recipient = await _load_request_and_recipient(row)
    if not share_request:
        raise ResourceNotFoundException("Pickup link not found")

    artifacts = None
    if row["dpa_accepted_at"] is not None:
        artifacts = await pickup.list_artifacts(row)

    body = {
        "request": _request_summary(row, share_request, recipient),
        "artifacts": artifacts,
    }
    return _json_with_headers(body)


@router.post("/{token}/accept-dpa")
async def pickup_accept_dpa(
    token: str,
    request: Request,
    pickup: PickupService = Depends(get_pickup_service),
):
    _rate_limit(request, token)
    row = await pickup.verify_token(token)
    row = await pickup.accept_dpa(row, client_ip(request), user_agent(request))
    share_request, recipient = await _load_request_and_recipient(row)
    artifacts = await pickup.list_artifacts(row)
    body = {
        "request": _request_summary(row, share_request, recipient),
        "artifacts": artifacts,
    }
    return _json_with_headers(body)


@router.get("/{token}/files/{file_id}/download")
async def pickup_download(
    token: str,
    file_id: UUID,
    request: Request,
    pickup: PickupService = Depends(get_pickup_service),
):
    _rate_limit(request, token)
    row = await pickup.verify_token(token)
    if row["dpa_accepted_at"] is None:
        # Force DPA acceptance before any download.
        from app.utils.exceptions import ForbiddenException
        raise ForbiddenException("You must accept the data-sharing agreement first")
    url = await pickup.generate_download_url(row, file_id, client_ip(request))
    resp = RedirectResponse(url=url, status_code=302)
    for k, v in _SECURITY_HEADERS.items():
        resp.headers[k] = v
    return resp


# ---------------------------------------------------------------------------
# Internal — JSON response helper that also sets the security headers.
# ---------------------------------------------------------------------------

from fastapi.responses import JSONResponse
from datetime import datetime


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Unserializable: {type(obj)}")


def _json_with_headers(body: dict) -> JSONResponse:
    import json
    payload = json.loads(json.dumps(body, default=_json_default))
    resp = JSONResponse(content=payload)
    for k, v in _SECURITY_HEADERS.items():
        resp.headers[k] = v
    return resp
