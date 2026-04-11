import logging

from app.gateways.cache_gateway import CacheGateway
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.products.data_sharing.services.notification_service import NotificationService
from app.utils.timezone import now

logger = logging.getLogger(__name__)


async def run_sla_check() -> None:
    repo = WorkflowRepository()
    cache = CacheGateway()
    audit = AuditService()
    notification = NotificationService()

    overdue_steps = await repo.find_overdue_steps()
    logger.info(f"SLA check: found {len(overdue_steps)} overdue steps")

    for step in overdue_steps:
        cache_key = f"dsplatform:sla_escalated:{step['id']}"
        if cache.sismember("dsplatform:sla_escalated", str(step["id"])):
            continue

        try:
            await repo.update_step(step["id"], escalated_at=now())
            cache.sadd("dsplatform:sla_escalated", str(step["id"]))

            if step.get("assignee_user_id"):
                await notification.create_notification(
                    user_id=step["assignee_user_id"],
                    tenant_id=0,  # Would need request lookup for real tenant_id
                    type="sla_breach",
                    title=f"SLA breached for step: {step.get('name', 'Unknown')}",
                    request_id=step["request_id"],
                )

            await audit.log(
                tenant_id=0,
                action_type="step.sla_breached",
                resource_type="workflow_step",
                resource_id=str(step["id"]),
                request_id=step["request_id"],
            )
            logger.info(f"Escalated overdue step {step['id']}")
        except Exception as e:
            logger.error(f"Failed to escalate step {step['id']}: {e}")
