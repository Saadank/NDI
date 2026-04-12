from app.platform.enums.platform_role import PlatformRole
from app.products.data_sharing.enums.sharing_role import SharingRole
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


def _is_admin(auth_user: AuthUser) -> bool:
    return auth_user.platform_role in ADMIN_ROLES


def _role(auth_user: AuthUser) -> str | None:
    return auth_user.product_role


# ---------------------------------------------------------------------------
# Request visibility
# ---------------------------------------------------------------------------

def can_see_all_requests(auth_user: AuthUser) -> bool:
    """platform_admin, org_admin, dpo see all tenant requests."""
    if _is_admin(auth_user):
        return True
    return _role(auth_user) == SharingRole.DPO


def can_see_assigned_requests(auth_user: AuthUser) -> bool:
    """data_owner sees only requests with workflow steps assigned to their role."""
    return _role(auth_user) == SharingRole.DATA_OWNER


def can_see_received_requests(auth_user: AuthUser) -> bool:
    """receiver sees only requests sent to them."""
    return _role(auth_user) == SharingRole.RECEIVER


def can_see_own_requests_only(auth_user: AuthUser) -> bool:
    """requester sees only their own requests."""
    return _role(auth_user) == SharingRole.REQUESTER


# ---------------------------------------------------------------------------
# Request CRUD
# ---------------------------------------------------------------------------

def can_create_request(auth_user: AuthUser) -> bool:
    if _is_admin(auth_user):
        return True
    return _role(auth_user) in (SharingRole.DPO, SharingRole.DATA_OWNER, SharingRole.REQUESTER)


def can_submit_request(auth_user: AuthUser, request: dict) -> bool:
    if _is_admin(auth_user):
        return True
    # dpo and data_owner can submit only their own requests
    if _role(auth_user) in (SharingRole.DPO, SharingRole.DATA_OWNER):
        return request["created_by"] == auth_user.user_id
    if _role(auth_user) == SharingRole.REQUESTER:
        return request["requester_id"] == auth_user.user_id
    return False


def can_cancel_request(auth_user: AuthUser, request: dict) -> bool:
    if _is_admin(auth_user):
        return True
    if _role(auth_user) in (SharingRole.DPO, SharingRole.DATA_OWNER):
        return request["created_by"] == auth_user.user_id
    if _role(auth_user) == SharingRole.REQUESTER:
        return request["requester_id"] == auth_user.user_id
    return False


def can_view_request(auth_user: AuthUser, request: dict) -> bool:
    """Check if user can view a specific request."""
    if can_see_all_requests(auth_user):
        return True
    if can_see_own_requests_only(auth_user):
        return request["requester_id"] == auth_user.user_id
    # receiver can view if request was sent to them (receiving_tenant_id)
    if can_see_received_requests(auth_user):
        return request.get("receiving_tenant_id") == auth_user.tenant_id
    # data_owner: allowed at service level via assigned step check
    if can_see_assigned_requests(auth_user):
        return True  # further filtered at service level
    return False


# ---------------------------------------------------------------------------
# Approval / workflow steps
# ---------------------------------------------------------------------------

def can_approve_step(auth_user: AuthUser, step: dict, request: dict) -> bool:
    if _is_admin(auth_user):
        return True
    if _role(auth_user) == SharingRole.DPO:
        return True
    if _role(auth_user) == SharingRole.DATA_OWNER:
        return step.get("assignee_role") == SharingRole.DATA_OWNER
    if _role(auth_user) == SharingRole.RECEIVER:
        return request.get("receiving_tenant_id") == auth_user.tenant_id
    return False


# ---------------------------------------------------------------------------
# Management capabilities
# ---------------------------------------------------------------------------

def can_manage_workflows(auth_user: AuthUser) -> bool:
    if _is_admin(auth_user):
        return True
    return _role(auth_user) == SharingRole.DPO


def can_manage_users(auth_user: AuthUser) -> bool:
    if _is_admin(auth_user):
        return True
    return _role(auth_user) == SharingRole.DPO


def can_view_audit_logs(auth_user: AuthUser) -> bool:
    if _is_admin(auth_user):
        return True
    return _role(auth_user) == SharingRole.DPO


def can_manage_connections(auth_user: AuthUser) -> bool:
    return _is_admin(auth_user)


def can_manage_schemas(auth_user: AuthUser) -> bool:
    return _is_admin(auth_user)


# ---------------------------------------------------------------------------
# Guard helper — raises ForbiddenException
# ---------------------------------------------------------------------------

def require(allowed: bool, message: str = "You do not have permission to perform this action") -> None:
    if not allowed:
        raise ForbiddenException(message)
