"""Permissions for the Data Quality product.

BRD §3 says all DQ team members share one role with no functional restrictions.
The IDQP BRD does not impose the data-controller / data-processor firewall that
data_sharing applies to platform admins (BRD §2.1 of the data-sharing BRD), so
platform admins are allowed here as a convenience for setup and operations.
Anyone whose tenant has data_quality enabled and who is an org admin, platform
admin, or holds the product role 'dq_team_member' can use the product.
"""

from app.platform.enums.platform_role import PlatformRole
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

DQ_TEAM_ROLE = "dq_team_member"

_ADMIN_ROLES = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


def can_use_dq(auth_user: AuthUser) -> bool:
    if auth_user.platform_role in _ADMIN_ROLES:
        return True
    return auth_user.product_role == DQ_TEAM_ROLE


def can_manage_connections(auth_user: AuthUser) -> bool:
    """DQ inherits the org-admin posture for source-DB credentials."""
    return auth_user.platform_role in _ADMIN_ROLES


def require(allowed: bool, message: str = "You do not have permission to perform this action") -> None:
    if not allowed:
        raise ForbiddenException(message)
