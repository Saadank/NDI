import logging
from uuid import UUID

from app.platform.services.audit_service import AuditService
from app.platform.services.delegation_service import DelegationService
from app.products.data_sharing.permissions import can_approve_step, require
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.products.data_sharing.services.workflow_engine import WorkflowEngine
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException
from app.utils.timezone import now

logger = logging.getLogger(__name__)


class ApprovalService:

    def __init__(self) -> None:
        self.workflow_repo = WorkflowRepository()
        self.request_repo = ShareRequestRepository()
        self.workflow_engine = WorkflowEngine()
        self.audit = AuditService()
        self.delegation = DelegationService()

    async def _check_step_permission(self, request_id: UUID, step_id: UUID, auth_user: AuthUser) -> tuple[dict, dict]:
        step = await self.workflow_repo.find_step(step_id)
        request = await self.request_repo.find_by_id(request_id, auth_user.tenant_id)
        require(can_approve_step(auth_user, step, request), "You do not have permission to act on this step")
        # BRD §2.2 EC-02: the requester must never act on their own approval step.
        # submit_request already auto-delegates, but re-check at runtime in case
        # a workflow was built before the conflict rule shipped.
        if request.get("requester_id") == auth_user.user_id:
            raise ForbiddenException(
                "You cannot approve a step on a request you raised"
            )
        # If a specific user is assigned, the acting user must be that user OR
        # a currently-active delegate of that user (BRD §2.3).
        assignee_user_id = step.get("assignee_user_id")
        if assignee_user_id and assignee_user_id != auth_user.user_id:
            if not await self.delegation.can_act_for(auth_user.user_id, assignee_user_id):
                raise ForbiddenException(
                    "This step is assigned to another user and no active delegation applies"
                )
        return step, request

    async def _delegation_from(self, step: dict, auth_user: AuthUser) -> int | None:
        """Return the original assignee id if the acting user is a delegate."""
        assignee_user_id = step.get("assignee_user_id")
        if assignee_user_id and assignee_user_id != auth_user.user_id:
            return assignee_user_id
        return None

    async def approve(self, request_id: UUID, step_id: UUID, comment: str | None, auth_user: AuthUser) -> dict:
        step, _ = await self._check_step_permission(request_id, step_id, auth_user)
        if step["status"] != "pending":
            raise ValidationException("Step is not pending approval")

        delegated_from = await self._delegation_from(step, auth_user)
        updated_step = await self.workflow_repo.update_step(
            step_id, status="approved", decision="approved", comment=comment,
            completed_at=now(), completed_by=auth_user.user_id,
            delegated_from_user_id=delegated_from,
        )

        next_step = await self.workflow_engine.advance_workflow(request_id, step_id)
        if not next_step:
            await self.request_repo.update_status(request_id, "approved", auth_user.user_id)
            # Post-approval hook for external pickup-portal recipients.
            # Must not roll back the approval if it fails.
            try:
                from app.products.data_sharing.services.share_finalization_service import (
                    ShareFinalizationService,
                )
                await ShareFinalizationService().finalize_if_external(request_id, auth_user)
            except Exception as exc:
                logger.exception(
                    "Post-approval finalization failed for request %s: %s", request_id, exc
                )

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="step.approved", resource_type="workflow_step",
            resource_id=str(step_id), actor_id=auth_user.user_id, request_id=request_id,
            metadata={"comment": comment, "delegated_from_user_id": delegated_from},
        )
        return updated_step

    async def reject(self, request_id: UUID, step_id: UUID, comment: str, auth_user: AuthUser) -> dict:
        if not comment:
            raise ValidationException("Comment is required when rejecting")

        step, _ = await self._check_step_permission(request_id, step_id, auth_user)
        if step["status"] != "pending":
            raise ValidationException("Step is not pending approval")

        delegated_from = await self._delegation_from(step, auth_user)
        updated_step = await self.workflow_repo.update_step(
            step_id, status="rejected", decision="rejected", comment=comment,
            completed_at=now(), completed_by=auth_user.user_id,
            delegated_from_user_id=delegated_from,
        )
        await self.request_repo.update_status(request_id, "rejected", auth_user.user_id)

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="step.rejected", resource_type="workflow_step",
            resource_id=str(step_id), actor_id=auth_user.user_id, request_id=request_id,
            metadata={"comment": comment, "delegated_from_user_id": delegated_from},
        )
        return updated_step

    async def request_changes(self, request_id: UUID, step_id: UUID, comment: str, auth_user: AuthUser) -> dict:
        if not comment:
            raise ValidationException("Comment is required when requesting changes")

        step, _ = await self._check_step_permission(request_id, step_id, auth_user)
        if step["status"] != "pending":
            raise ValidationException("Step is not pending")

        delegated_from = await self._delegation_from(step, auth_user)
        updated_step = await self.workflow_repo.update_step(
            step_id, status="changes_requested", decision="changes_requested", comment=comment,
            completed_at=now(), completed_by=auth_user.user_id,
            delegated_from_user_id=delegated_from,
        )
        await self.request_repo.update_status(request_id, "draft", auth_user.user_id)

        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="step.changes_requested", resource_type="workflow_step",
            resource_id=str(step_id), actor_id=auth_user.user_id, request_id=request_id,
            metadata={"comment": comment, "delegated_from_user_id": delegated_from},
        )
        return updated_step


def get_approval_service() -> ApprovalService:
    return ApprovalService()
