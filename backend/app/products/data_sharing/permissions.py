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
    # Everyone can view their own requests
    if request["requester_id"] == auth_user.user_id:
        return True
    # Anyone in the receiver group can view (list query already filters by workflow status)
    if auth_user.group_id and request.get("receiver_group_id") == auth_user.group_id:
        return True
    # Receiver by tenant
    if can_see_received_requests(auth_user):
        if request.get("receiving_tenant_id") == auth_user.tenant_id:
            return True
    # data_owner: allowed at service level via assigned step check
    if can_see_assigned_requests(auth_user):
        return True
    return False


# ---------------------------------------------------------------------------
# Approval / workflow steps
# ---------------------------------------------------------------------------

def can_approve_step(auth_user: AuthUser, step: dict, request: dict) -> bool:
    if _is_admin(auth_user):
        return True
    role = _role(auth_user)
    assignee = step.get("assignee_role")
    if role == SharingRole.DPO:
        return assignee == SharingRole.DPO
    if role == SharingRole.DATA_OWNER:
        if assignee != SharingRole.DATA_OWNER:
            return False
        # Must be the specific data owner assigned to this step
        if step.get("assignee_user_id"):
            return step["assignee_user_id"] == auth_user.user_id
        return True  # fallback if no specific user assigned
    if role == SharingRole.RECEIVER:
        if assignee != SharingRole.RECEIVER:
            return False
        if auth_user.group_id and request.get("receiver_group_id") == auth_user.group_id:
            return True
        return request.get("receiving_tenant_id") == auth_user.tenant_id
    return False


# ---------------------------------------------------------------------------
# Management capabilities
# ---------------------------------------------------------------------------

def can_manage_workflows(auth_user: AuthUser) -> bool:
    return _is_admin(auth_user)


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


def can_browse_connections(auth_user: AuthUser) -> bool:
    """Anyone who can create a request needs to browse connections (read-only, no password)."""
    return can_create_request(auth_user)


def can_browse_schemas(auth_user: AuthUser) -> bool:
    """Anyone who can create a request needs to browse schemas to pick tables/columns."""
    return can_create_request(auth_user)


# ---------------------------------------------------------------------------
# Guard helper — raises ForbiddenException
# ---------------------------------------------------------------------------

def require(allowed: bool, message: str = "You do not have permission to perform this action") -> None:
    if not allowed:
        raise ForbiddenException(message)
