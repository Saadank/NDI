import logging
from uuid import UUID

from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.services.workflow_engine import WorkflowEngine
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException
from app.utils.pagination import get_pagination_data

logger = logging.getLogger(__name__)


class ShareRequestService:

    def __init__(self) -> None:
        self.repo = ShareRequestRepository()
        self.workflow_engine = WorkflowEngine()
        self.audit = AuditService()

    async def create_draft(self, data: dict, auth_user: AuthUser) -> dict:
        tenant_id = auth_user.tenant_id
        request_number = await self.repo.next_request_number(tenant_id)

        request = await self.repo.create(
            tenant_id=tenant_id,
            request_number=request_number,
            title=data["title"],
            purpose=data["purpose"],
            legal_basis=data.get("legal_basis", ""),
            sharing_type=data.get("sharing_type", "internal"),
            data_classification=data.get("data_classification", "internal"),
            personal_data_involved=data.get("personal_data_involved", False),
            estimated_data_subjects=data.get("estimated_data_subjects"),
            data_subject_categories=data.get("data_subject_categories"),
            source_description=data.get("source_description"),
            requester_id=auth_user.user_id,
            receiving_tenant_id=data.get("receiving_tenant_id"),
            created_by=auth_user.user_id,
            dpia_confirmed=data.get("dpia_confirmed", False),
        )

        await self.audit.log(
            tenant_id=tenant_id, action_type="request.created", resource_type="share_request",
            resource_id=str(request["id"]), actor_id=auth_user.user_id,
            after_state=request, request_id=request["id"],
        )
        return request

    async def submit_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        tenant_id = auth_user.tenant_id
        request = await self.repo.find_by_id(request_id, tenant_id)

        if request["status"] != "draft":
            raise ValidationException("Only draft requests can be submitted")

        # PDPL validation
        if request["personal_data_involved"]:
            if not request.get("legal_basis"):
                raise ValidationException("Legal basis is required for personal data")
            if not request.get("estimated_data_subjects"):
                raise ValidationException("Estimated data subjects is required for personal data")
        if request["data_classification"] == "sensitive" and not request.get("dpia_confirmed"):
            raise ValidationException("DPIA confirmation required for sensitive data")

        # Select matching workflow template and create steps
        template = await self.workflow_engine.select_template(
            request["sharing_type"], request["data_classification"], tenant_id
        )
        if template:
            await self.workflow_engine.create_workflow_steps(request_id, template)
            await self.repo.update(request_id, workflow_template_id=template["id"])

        updated = await self.repo.update_status(request_id, "submitted", auth_user.user_id)

        await self.audit.log(
            tenant_id=tenant_id, action_type="request.submitted", resource_type="share_request",
            resource_id=str(request_id), actor_id=auth_user.user_id, request_id=request_id,
        )
        return updated

    async def get_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        return await self.repo.find_by_id(request_id, auth_user.tenant_id)

    async def list_requests(self, auth_user: AuthUser, status: str | None = None, page: int = 1, limit: int = 20) -> dict:
        tenant_id = auth_user.tenant_id
        requests = await self.repo.find_by_tenant(tenant_id, status, page, limit)
        total = await self.repo.count_by_tenant(tenant_id, status)
        pagination = get_pagination_data(limit, page, total)
        return {"data": requests, **pagination}

    async def cancel_request(self, request_id: UUID, auth_user: AuthUser) -> dict:
        request = await self.repo.find_by_id(request_id, auth_user.tenant_id)
        if request["status"] in ("completed", "cancelled"):
            raise ValidationException("Cannot cancel a completed or already cancelled request")
        updated = await self.repo.update_status(request_id, "cancelled", auth_user.user_id)
        await self.audit.log(
            tenant_id=auth_user.tenant_id, action_type="request.cancelled", resource_type="share_request",
            resource_id=str(request_id), actor_id=auth_user.user_id, request_id=request_id,
        )
        return updated


def get_share_request_service() -> ShareRequestService:
    return ShareRequestService()
