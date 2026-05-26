"""Permission helpers for NDMO Compliance.

MVP scope (per the project spec): only ONE actor — "Compliance Analyst".
Stored in t_user_product_roles with role='compliance_analyst' against the
'ndmo' product.

Routers/services should call ``require_compliance_analyst(auth_user)`` to
401/403 anonymous or wrong-role callers.  At this MVP stage every product
endpoint requires the same role, so the check is a one-liner.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.structures.auth_user import AuthUser

ROLE_COMPLIANCE_ANALYST = "compliance_analyst"


def require_compliance_analyst(auth_user: AuthUser) -> None:
    """Raise 403 unless the caller has the Compliance Analyst product role.

    Reads ``auth_user.product_role`` which the security middleware fills in
    from t_user_product_roles for the currently-targeted product.
    """
    role = getattr(auth_user, "product_role", None)
    if role != ROLE_COMPLIANCE_ANALYST:
        raise HTTPException(
            status_code=403,
            detail="Compliance Analyst role required to perform this action.",
        )
