"""Unit tests for models and utilities that don't require DB."""
import pytest
import math

from app.structures.auth_user import AuthUser
from app.platform.enums.platform_role import PlatformRole
from app.platform.enums.product_slug import ProductSlug
from app.products.data_sharing.enums.sharing_role import SharingRole
from app.products.data_sharing.enums.request_status import RequestStatus
from app.products.data_sharing.enums.data_classification import DataClassification
from app.products.data_sharing.enums.legal_basis import LegalBasis
from app.utils.exceptions import (
    BaseAppException, ValidationException, UnauthorizedException,
    ForbiddenException, ResourceNotFoundException, ConflictException, ExpiredException,
)
from app.utils.pagination import get_pagination_data
from app.utils.timezone import now, RIYADH_TZ


def test_auth_user_model():
    user = AuthUser(
        user_id=1,
        keycloak_id="kc-123",
        tenant_id=1,
        platform_role=PlatformRole.PLATFORM_ADMIN,
    )
    assert user.user_id == 1
    assert user.platform_role == PlatformRole.PLATFORM_ADMIN
    assert user.product_role is None
    assert user.current_product is None


def test_platform_roles():
    assert PlatformRole.PLATFORM_ADMIN.value == "platform_admin"
    assert PlatformRole.ORG_ADMIN.value == "org_admin"


def test_product_slugs():
    assert ProductSlug.DATA_SHARING.value == "data_sharing"
    assert ProductSlug.DATA_QUALITY.value == "data_quality"
    assert ProductSlug.NDMO.value == "ndmo"
    assert ProductSlug.DSR.value == "dsr"


def test_sharing_roles():
    assert len(SharingRole) == 5
    assert SharingRole.DPO.value == "dpo"


def test_request_statuses():
    assert RequestStatus.DRAFT.value == "draft"
    assert RequestStatus.SUBMITTED.value == "submitted"
    assert RequestStatus.APPROVED.value == "approved"
    assert RequestStatus.REJECTED.value == "rejected"


def test_data_classification():
    assert DataClassification.SENSITIVE.value == "sensitive"
    assert DataClassification.PUBLIC.value == "public"


def test_legal_basis():
    assert LegalBasis.CONSENT.value == "consent"
    assert LegalBasis.LEGAL_OBLIGATION.value == "legal_obligation"


def test_exceptions():
    assert ValidationException("bad").status_code == 400
    assert UnauthorizedException("no").status_code == 401
    assert ForbiddenException("denied").status_code == 403
    assert ResourceNotFoundException("gone").status_code == 404
    assert ConflictException("dup").status_code == 409
    assert ExpiredException("old").status_code == 410


def test_pagination():
    result = get_pagination_data(limit=10, page=1, total=25)
    p = result["pagination"]
    assert p["total_pages"] == 3
    assert p["next_page"] == 2
    assert p["previous_page"] is None
    assert p["page"] == 1

    result2 = get_pagination_data(limit=10, page=3, total=25)
    p2 = result2["pagination"]
    assert p2["next_page"] is None
    assert p2["previous_page"] == 2


def test_pagination_empty():
    result = get_pagination_data(limit=10, page=1, total=0)
    assert result["pagination"]["total_pages"] == 0
    assert result["pagination"]["next_page"] is None


def test_timezone_now():
    dt = now()
    assert dt.tzinfo is not None
    assert str(dt.tzinfo) == "Asia/Riyadh"
