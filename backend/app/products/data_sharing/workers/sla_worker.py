"""SLA escalation ladder worker (BRD §2.3, EC-05).

State machine for a pending step:
  level 0 → 1:  sla_deadline has passed (first breach; Day 3 in the BRD)
  level 1 → 2:  2 business days after first escalation (Day 5)
  level 2 → 3:  2 more business days — step is stalled and request is cancelled (Day 7)

The worker is idempotent: every pass moves steps forward at most one level.
"""
import logging

from app.gateways.cache_gateway import CacheGateway
from app.platform.repositories.user_repository import UserRepository
from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.share_request_repository import ShareRequestRepository
from app.products.data_sharing.repositories.workflow_repository import WorkflowRepository
from app.products.data_sharing.services.notification_service import NotificationService
from app.utils.business_calendar import BusinessCalendar
from app.utils.timezone import now

logger = logging.getLogger(__name__)

# BRD §2.3 gives absolute Day-3 / Day-5 / Day-7 milestones.
# The deltas below are relative to the initial breach.
_LEVEL_2_BUSINESS_DAYS = 2  # Day 3 → Day 5
_LEVEL_3_BUSINESS_DAYS = 2  # Day 5 → Day 7


async def _find_org_admin_ids(tenant_id: int) -> list[int]:
    admin = await UserRepository().find_first_org_admin(tenant_id)
    return [admin["id"]] if admin else []


async def _request_context(step: dict, request_repo: ShareRequestRepository) -> dict | None:
    row = await request_repo._fetch_row_optional(
        "SELECT * FROM t_share_requests WHERE id = $1", (step["request_id"],)
    )
    return row


async def _escalate_first_breach(
    step: dict,
    workflow_repo: WorkflowRepository,
    request_repo: ShareRequestRepository,
    notification: NotificationService,
    audit: AuditService,
) -> None:
    request = await _request_context(step, request_repo)
    tenant_id = request["tenant_id"] if request else 0

    await workflow_repo.update_step(
        step["id"], escalated_at=now(), escalation_level=1,
    )

    # Notify the assignee and the Org Admin.
    notify_ids: list[int] = []
    if step.get("assignee_user_id"):
        notify_ids.append(step["assignee_user_id"])
    notify_ids.extend(await _find_org_admin_ids(tenant_id))

    for user_id in set(notify_ids):
        await notification.create_notification(
            user_id=user_id,
            tenant_id=tenant_id,
            type="sla_breach",
            title=f"SLA breached on step: {step.get('name') or 'Approval'}",
            request_id=step["request_id"],
        )

    await audit.log(
        tenant_id=tenant_id,
        action_type="step.sla_breached",
        resource_type="workflow_step",
        resource_id=str(step["id"]),
        request_id=step["request_id"],
        metadata={"escalation_level": 1},
    )


async def _escalate_second(
    step: dict,
    workflow_repo: WorkflowRepository,
    request_repo: ShareRequestRepository,
    notification: NotificationService,
    audit: AuditService,
) -> None:
    request = await _request_context(step, request_repo)
    if not request:
        return
    tenant_id = request["tenant_id"]

    # Only fire when enough business days have elapsed since the first breach.
    cal = BusinessCalendar(tenant_id)
    elapsed = await cal.working_days_between(step["escalated_at"], now())
    if elapsed < _LEVEL_2_BUSINESS_DAYS:
        return

    await workflow_repo.update_step(
        step["id"], second_escalated_at=now(), escalation_level=2,
    )

    for admin_id in await _find_org_admin_ids(tenant_id):
        await notification.create_notification(
            user_id=admin_id,
            tenant_id=tenant_id,
            type="sla_second_escalation",
            title=(
                f"Action required: step stalled. Reassign or the request "
                f"will be auto-cancelled on Day 7."
            ),
            request_id=step["request_id"],
        )

    await audit.log(
        tenant_id=tenant_id,
        action_type="step.second_escalation",
        resource_type="workflow_step",
        resource_id=str(step["id"]),
        request_id=step["request_id"],
        metadata={"escalation_level": 2},
    )


async def _auto_cancel(
    step: dict,
    workflow_repo: WorkflowRepository,
    request_repo: ShareRequestRepository,
    notification: NotificationService,
    audit: AuditService,
) -> None:
    request = await _request_context(step, request_repo)
    if not request:
        return
    tenant_id = request["tenant_id"]
    cal = BusinessCalendar(tenant_id)
    anchor = step.get("second_escalated_at") or step["escalated_at"]
    elapsed = await cal.working_days_between(anchor, now())
    if elapsed < _LEVEL_3_BUSINESS_DAYS:
        return

    # Mark step stalled and cancel the parent request.
    await workflow_repo.update_step(
        step["id"], stalled_at=now(), escalation_level=3, status="cancelled",
    )
    await request_repo.update_status(step["request_id"], "cancelled", None)

    # Notify requester and Org Admin.
    recipients = {request["requester_id"], *(await _find_org_admin_ids(tenant_id))}
    for user_id in recipients:
        if not user_id:
            continue
        await notification.create_notification(
            user_id=user_id,
            tenant_id=tenant_id,
            type="request_auto_cancelled",
            title="Request auto-cancelled after 7 days without action",
            request_id=step["request_id"],
        )

    await audit.log(
        tenant_id=tenant_id,
        action_type="request.auto_cancelled",
        resource_type="share_request",
        resource_id=str(step["request_id"]),
        request_id=step["request_id"],
        metadata={"reason": "sla_stalled_day_7", "step_id": str(step["id"])},
    )


async def run_sla_check() -> None:
    workflow_repo = WorkflowRepository()
    request_repo = ShareRequestRepository()
    cache = CacheGateway()
    audit = AuditService()
    notification = NotificationService()

    # --- Level 1: first breach ---
    overdue = await workflow_repo.find_overdue_steps()
    logger.info("SLA check (level 1): %d overdue steps", len(overdue))
    for step in overdue:
        if cache.sismember("dsplatform:sla_escalated", str(step["id"])):
            continue
        try:
            await _escalate_first_breach(step, workflow_repo, request_repo, notification, audit)
            cache.sadd("dsplatform:sla_escalated", str(step["id"]))
        except Exception as e:
            logger.error("Level-1 escalation failed for step %s: %s", step["id"], e)

    # --- Level 2: second escalation ---
    for step in await workflow_repo.find_steps_awaiting_second_escalation():
        try:
            await _escalate_second(step, workflow_repo, request_repo, notification, audit)
        except Exception as e:
            logger.error("Level-2 escalation failed for step %s: %s", step["id"], e)

    # --- Level 3: auto-cancel ---
    for step in await workflow_repo.find_steps_awaiting_stall():
        try:
            await _auto_cancel(step, workflow_repo, request_repo, notification, audit)
        except Exception as e:
            logger.error("Auto-cancel failed for step %s: %s", step["id"], e)
