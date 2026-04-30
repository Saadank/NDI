"""Governed exception engine — Phase 1, Step 5 (BRD §4.8 / FR-EXC).

Lets a DQ team acknowledge legitimate violations on a rule. The validator
keeps recording issues (raw_score sees them); ScoringService consults active
exceptions when computing governed_score and treats covered violations as
PASS up to the optional ceiling.

Flow on create:
  1. Validate the rule belongs to the profile (and tenant).
  2. Revoke any prior active exception for that rule (partial unique index).
  3. Insert the new active exception.
  4. If a successful scan exists, re-score it so governed_score updates
     immediately. Failure to re-score is logged but does not undo the create.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.active_rule_repository import (
    ActiveRuleRepository,
)
from app.products.data_quality.repositories.exception_repository import (
    ExceptionRepository,
)
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_quality.repositories.scan_repository import ScanRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import (
    ForbiddenException, ResourceNotFoundException, ValidationException,
)

logger = logging.getLogger(__name__)

_VALID_REASONS = {
    "legacy_data", "business_accepted", "in_progress", "data_provider", "other",
}
_MAX_HORIZON_DAYS = 365  # exceptions can't be set further than 1 year out


class ExceptionService:

    def __init__(self) -> None:
        self.repo = ExceptionRepository()
        self.rule_repo = ActiveRuleRepository()
        self.profile_repo = ProfileRepository()
        self.scan_repo = ScanRepository()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_for_profile(
        self, *, profile_id: int, include_revoked: bool, auth_user: AuthUser,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        # Check profile belongs to tenant — surfaces a clear 404 instead of an
        # empty list when the caller passes a foreign profile_id.
        profile = await self.profile_repo.find_by_id(profile_id, auth_user.tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")
        return await self.repo.list_for_profile(
            tenant_id=auth_user.tenant_id, profile_id=profile_id,
            include_revoked=include_revoked,
        )

    async def get_exception(self, exception_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.repo.find_by_id(exception_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Exception not found")
        return row

    # ------------------------------------------------------------------
    # Mutations — gated to admins (governance setting).
    # ------------------------------------------------------------------

    async def create_exception(
        self, *, profile_id: int, active_rule_id: int,
        reason_category: str, explanation: str,
        violation_count_ceiling: int | None,
        expires_at: datetime, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._require_admin(auth_user)
        self._validate_reason(reason_category)
        if not explanation or not explanation.strip():
            raise ValidationException("explanation is required")
        if violation_count_ceiling is not None and violation_count_ceiling < 0:
            raise ValidationException("violation_count_ceiling must be >= 0")

        now = _utcnow()
        if expires_at <= now:
            raise ValidationException("expires_at must be in the future")
        if expires_at > now + timedelta(days=_MAX_HORIZON_DAYS):
            raise ValidationException(
                f"expires_at must be within {_MAX_HORIZON_DAYS} days from now"
            )

        # Profile + rule ownership check.
        profile = await self.profile_repo.find_by_id(profile_id, auth_user.tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")
        rule = await self.rule_repo.find_by_id(active_rule_id, auth_user.tenant_id)
        if not rule:
            raise ResourceNotFoundException("Active rule not found")
        if rule.get("profile_id") != profile_id:
            raise ValidationException(
                "Active rule does not belong to the given profile"
            )

        # Replace any prior active exception (partial unique index requires
        # us to mark the old row revoked before inserting the new one).
        await self.repo.revoke_active_for_rule(
            tenant_id=auth_user.tenant_id, active_rule_id=active_rule_id,
            user_id=auth_user.user_id, reason="Replaced by new exception",
        )

        row = await self.repo.insert_active(
            tenant_id=auth_user.tenant_id, profile_id=profile_id,
            active_rule_id=active_rule_id,
            reason_category=reason_category,
            explanation=explanation.strip(),
            violation_count_ceiling=violation_count_ceiling,
            expires_at=expires_at, created_by=auth_user.user_id,
        )
        await self._rescore_latest(profile_id, auth_user.tenant_id)
        return row

    async def revoke(
        self, exception_id: int, *, reason: str | None, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._require_admin(auth_user)
        existing = await self.repo.find_by_id(exception_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Exception not found")
        if existing["status"] != "active":
            raise ValidationException("Only active exceptions can be revoked")

        row = await self.repo.revoke(
            exception_id, auth_user.tenant_id,
            user_id=auth_user.user_id, reason=reason,
        )
        await self._rescore_latest(existing["profile_id"], auth_user.tenant_id)
        return row

    async def extend(
        self, exception_id: int, *, days: int | None, until: datetime | None,
        auth_user: AuthUser,
    ) -> dict:
        """Bump expires_at on an active exception. Either bump by `days` from
        the current expiry, or set an explicit `until` timestamp."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._require_admin(auth_user)
        existing = await self.repo.find_by_id(exception_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Exception not found")
        if existing["status"] != "active":
            raise ValidationException("Only active exceptions can be extended")

        if until is None and not days:
            raise ValidationException("Provide either `days` or `until`")
        new_expiry = until or (existing["expires_at"] + timedelta(days=int(days)))
        now = _utcnow()
        if new_expiry <= now:
            raise ValidationException("New expiry must be in the future")
        if new_expiry > now + timedelta(days=_MAX_HORIZON_DAYS):
            raise ValidationException(
                f"New expiry must be within {_MAX_HORIZON_DAYS} days from now"
            )

        row = await self.repo.update_expiry(
            exception_id, auth_user.tenant_id, new_expires_at=new_expiry,
        )
        await self._rescore_latest(existing["profile_id"], auth_user.tenant_id)
        return row

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_reason(reason: str) -> None:
        if reason not in _VALID_REASONS:
            raise ValidationException(
                f"reason_category must be one of {sorted(_VALID_REASONS)}"
            )

    @staticmethod
    def _require_admin(auth_user: AuthUser) -> None:
        from app.platform.enums.platform_role import PlatformRole
        if auth_user.platform_role not in (
            PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN,
        ):
            raise ForbiddenException(
                "Only org or platform admins can manage DQ exceptions"
            )

    async def _rescore_latest(self, profile_id: int, tenant_id: int) -> None:
        """Best-effort: re-score the profile's most recent successful scan so
        governed_score updates immediately on the Metrics tab. Logs and
        swallows failures — the exception write already succeeded."""
        try:
            scans = await self.scan_repo.list_for_tenant(
                tenant_id, profile_id=profile_id, limit=20,
            )
            success = next((s for s in scans if s["status"] == "success"), None)
            if not success:
                return
            from app.products.data_quality.services.scoring_service import (
                get_scoring_service,
            )
            await get_scoring_service().score_scan(
                tenant_id=tenant_id, profile_id=profile_id, scan_id=success["id"],
            )
        except Exception:  # noqa: BLE001
            logger.exception("Re-score after exception change failed (profile=%s)", profile_id)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_exception_service() -> ExceptionService:
    return ExceptionService()
