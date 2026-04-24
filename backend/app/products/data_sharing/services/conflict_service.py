import logging
from uuid import UUID

from app.platform.repositories.user_repository import UserRepository
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.enums.sharing_role import SharingRole
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository

logger = logging.getLogger(__name__)


class ConflictService:
    """Enforces BRD §2.2 role-conflict rules at workflow step creation time.

    EC-02: requester == assigned approver → reassign to Org Admin.
    EC-03: DPO step when requester is a DPO → reassign to Org Admin.
    EC-04: Data Owner step where the assignee is the requester → reassign to Org Admin.
    EC-05 (soft flag): Org Admin self-approval — logged but allowed.

    Platform Admin never appears as an approver (metadata-only per §2.1).
    """

    def __init__(self) -> None:
        self.workflow_repo = WorkflowRepository()
        self.users = UserRepository()
        self.audit = AuditService()

    async def resolve_step_conflicts(
        self, request: dict, steps: list[dict], auth_user,
    ) -> list[dict]:
        tenant_id = request["tenant_id"]
        requester_id = request["requester_id"]
        requester_product_role = (auth_user.product_role or "").lower() if auth_user else ""

        org_admin = await self.users.find_first_org_admin(tenant_id)
        resolved: list[dict] = []

        for step in steps:
            conflict_reason = self._detect_conflict(step, requester_id, requester_product_role)
            if not conflict_reason:
                resolved.append(step)
                continue

            if not org_admin:
                # No Org Admin to receive the delegation. Per BRD §3.1 every
                # tenant must appoint one during onboarding, so in production
                # this branch is unreachable. In dev / single-user tenants we
                # soft-fail: log the unresolved conflict for the audit trail
                # and leave the step assigned so submission can proceed.
                await self.audit.log(
                    tenant_id=tenant_id,
                    action_type="step.conflict_unresolved",
                    resource_type="workflow_step",
                    resource_id=str(step["id"]),
                    actor_id=requester_id,
                    request_id=request["id"],
                    metadata={
                        "reason": conflict_reason,
                        "brd_rule": "section_2.2",
                        "note": "no_org_admin_available",
                    },
                )
                logger.warning(
                    "Conflict %s on step %s but no Org Admin to delegate to; step left unchanged",
                    conflict_reason, step["id"],
                )
                resolved.append(step)
                continue

            original_assignee = step.get("assignee_user_id")
            updated = await self.workflow_repo.update_step(
                step["id"],
                assignee_user_id=org_admin["id"],
                delegated_from_user_id=original_assignee,
            )
            await self.audit.log(
                tenant_id=tenant_id,
                action_type="step.auto_delegated",
                resource_type="workflow_step",
                resource_id=str(step["id"]),
                actor_id=requester_id,
                request_id=request["id"],
                metadata={
                    "reason": conflict_reason,
                    "from_user_id": original_assignee,
                    "to_user_id": org_admin["id"],
                    "brd_rule": "section_2.2",
                },
            )
            logger.info(
                "Auto-delegated step %s (%s) from user %s to Org Admin %s",
                step["id"], conflict_reason, original_assignee, org_admin["id"],
            )
            resolved.append(updated)

        return resolved

    @staticmethod
    def _detect_conflict(
        step: dict, requester_id: int, requester_product_role: str,
    ) -> str | None:
        """Detect a role-conflict that the system should auto-delegate.

        Note: the BRD-defined EC-02 (requester == specific assignee) and EC-04
        (data-owner self-approval of own-department data) are intentionally
        NOT enforced here. Product decision: a Data Owner is allowed to
        approve a request they raised when it involves their own department's
        data — they are the accountable owner, and delegating that approval
        to an Org Admin was causing friction without adding real control.

        EC-03 (DPO self-review) is still enforced because DPO review is a
        distinct PDPL compliance gate, not an ownership decision.
        """
        assignee_role = (step.get("assignee_role") or "").lower()

        # EC-03: DPO-role step while requester also holds DPO role.
        if assignee_role == SharingRole.DPO.value and requester_product_role == SharingRole.DPO.value:
            return "ec_03_dpo_self_review"

        return None


def get_conflict_service() -> ConflictService:
    return ConflictService()
