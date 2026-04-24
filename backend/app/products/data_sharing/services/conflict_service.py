import logging
from uuid import UUID

from app.platform.repositories.user_repository import UserRepository
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.enums.sharing_role import SharingRole
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.utils.exceptions import ValidationException

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
                # Cannot delegate if no Org Admin exists — hard fail on submit
                # so the Platform Admin can fix the org before any request goes out.
                raise ValidationException(
                    "Role conflict detected but no Org Admin is available to take over: "
                    f"{conflict_reason}"
                )

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
        assignee_role = (step.get("assignee_role") or "").lower()
        assignee_user_id = step.get("assignee_user_id")

        # EC-02: the specific person assigned is the requester.
        if assignee_user_id and assignee_user_id == requester_id:
            return "ec_02_requester_is_assignee"

        # EC-03: DPO-role step while requester also holds DPO role.
        if assignee_role == SharingRole.DPO.value and requester_product_role == SharingRole.DPO.value:
            return "ec_03_dpo_self_review"

        # EC-04: Data-owner step where requester holds the data_owner role
        # (the specific-assignee check in EC-02 already covers same-person).
        if (
            assignee_role == SharingRole.DATA_OWNER.value
            and requester_product_role == SharingRole.DATA_OWNER.value
            and assignee_user_id == requester_id
        ):
            return "ec_04_data_owner_self_approval"

        return None


def get_conflict_service() -> ConflictService:
    return ConflictService()
