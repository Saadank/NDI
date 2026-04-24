import logging
from datetime import datetime

from app.platform.repositories.user_repository import UserRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException
from app.utils.timezone import now

logger = logging.getLogger(__name__)


# Role seniority used to enforce BRD §2.3: "The delegate must hold the same or
# higher role in the system." Higher number = more senior.
# String keys (not enum refs) to keep this module free of cross-package imports
# that would otherwise create a circular dependency via the data-sharing package.
_PRODUCT_ROLE_RANK: dict[str, int] = {
    "requester": 1,
    "receiver": 1,
    "source": 2,
    "data_owner": 3,
    "dpo": 4,
}

_PLATFORM_ROLE_RANK: dict[str, int] = {
    "user": 0,
    "org_admin": 5,
    "platform_admin": 6,
}


def _rank(user: dict) -> int:
    plat = _PLATFORM_ROLE_RANK.get(user.get("platform_role") or "", 0)
    # product_role is resolved per request context; we approximate via the
    # user's assigned product role if it's on the record, otherwise 0.
    prod = _PRODUCT_ROLE_RANK.get(user.get("product_role") or "", 0)
    return max(plat, prod)


class DelegationService:

    def __init__(self) -> None:
        self.users = UserRepository()

    async def get_active_delegate(
        self, user_id: int, at: datetime | None = None,
    ) -> int | None:
        """Return the delegate's user_id if `user_id` has an active delegation at `at`."""
        user = await self.users.find_by_id(user_id)
        if not user:
            return None
        delegate_to = user.get("delegation_to_user_id")
        if not delegate_to:
            return None
        start = user.get("delegation_start")
        end = user.get("delegation_end")
        moment = at or now()
        if start and moment < start:
            return None
        if end and moment > end:
            return None
        return delegate_to

    async def can_act_for(
        self, actor_id: int, original_id: int, at: datetime | None = None,
    ) -> bool:
        """True if `actor_id` is `original_id` or a valid delegate of them."""
        if actor_id == original_id:
            return True
        delegate = await self.get_active_delegate(original_id, at)
        return delegate == actor_id

    async def set_delegation(
        self,
        auth_user: AuthUser,
        delegate_to_user_id: int | None,
        start: datetime | None,
        end: datetime | None,
        reason: str | None,
    ) -> dict:
        """Set, update, or clear the caller's own out-of-office delegation."""
        if delegate_to_user_id is None:
            # Clearing — allowed unconditionally.
            return await self.users.set_delegation(auth_user.user_id, None)

        if delegate_to_user_id == auth_user.user_id:
            raise ValidationException("You cannot delegate to yourself")

        if not start or not end:
            raise ValidationException("delegation_start and delegation_end are required")
        if end <= start:
            raise ValidationException("delegation_end must be after delegation_start")

        delegate = await self.users.find_by_id(delegate_to_user_id)
        if not delegate or delegate.get("tenant_id") != auth_user.tenant_id:
            raise ValidationException("Delegate must be a user in your organisation")
        if not delegate.get("is_active") or delegate.get("deleted_at"):
            raise ValidationException("Delegate must be an active user")

        me = await self.users.find_by_id(auth_user.user_id)
        # Delegate must be in the caller's department. If the caller has no
        # department yet, they cannot delegate — ask the Org Admin to assign one.
        my_group = (me or {}).get("group_id")
        if not my_group:
            raise ValidationException(
                "You must be assigned to a department before setting a delegation"
            )
        if delegate.get("group_id") != my_group:
            raise ValidationException(
                "Delegate must be in the same department as you"
            )
        # BRD §2.3: delegate must hold same or higher seniority.
        if me and _rank(delegate) < _rank(me):
            raise ForbiddenException(
                "Delegate must hold the same or higher role than you"
            )

        return await self.users.set_delegation(
            auth_user.user_id, delegate_to_user_id, start, end, reason,
        )


def get_delegation_service() -> DelegationService:
    return DelegationService()
