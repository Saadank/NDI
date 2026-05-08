from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class WorkflowRepository(PostgresqlAsyncRepository):

    # --- Templates ---

    async def find_template(self, sharing_type: str | None, data_classification: str | None, tenant_id: int) -> dict | None:
        conditions = ["tenant_id = $1", "is_active = TRUE"]
        args: list = [tenant_id]
        idx = 2
        if sharing_type:
            conditions.append(f"(sharing_type = ${idx} OR sharing_type IS NULL)")
            args.append(sharing_type)
            idx += 1
        if data_classification:
            conditions.append(f"(data_classification = ${idx} OR data_classification IS NULL)")
            args.append(data_classification)
            idx += 1
        where = " AND ".join(conditions)
        return await self._fetch_row_optional(
            f"SELECT * FROM t_workflow_templates WHERE {where} ORDER BY sharing_type DESC NULLS LAST, data_classification DESC NULLS LAST LIMIT 1",
            tuple(args),
        )

    async def find_template_steps(self, template_id: UUID) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_template_steps WHERE template_id = $1 ORDER BY step_order", (template_id,)
        )

    async def create_template(self, tenant_id: int, name: str, sharing_type: str | None, data_classification: str | None, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_workflow_templates (tenant_id, name, sharing_type, data_classification, created_by)
               VALUES ($1, $2, $3, $4, $5) RETURNING *""",
            (tenant_id, name, sharing_type, data_classification, created_by),
        )

    async def create_template_step(self, template_id: UUID, step_order: int, step_type: str, name: str,
                                   assignee_role: str | None, execution_mode: str, sla_days: int, condition_expr: str | None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_template_steps (template_id, step_order, step_type, name, assignee_role, execution_mode, sla_days, condition_expr)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *""",
            (template_id, step_order, step_type, name, assignee_role, execution_mode, sla_days, condition_expr),
        )

    async def update_template(self, template_id: UUID, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        args.append(template_id)
        return await self._fetch_row(
            f"UPDATE t_workflow_templates SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

    async def delete_template_steps(self, template_id: UUID) -> None:
        await self._execute("DELETE FROM t_template_steps WHERE template_id = $1", (template_id,))

    async def delete_template(self, template_id: UUID) -> None:
        """Hard-delete a workflow template. Cascades through template steps
        first, then drops the template row itself. Caller must have already
        verified there are no in-flight requests still bound to it (or
        nulled their workflow_template_id)."""
        await self._execute("DELETE FROM t_template_steps WHERE template_id = $1", (template_id,))
        await self._execute("DELETE FROM t_workflow_templates WHERE id = $1", (template_id,))

    async def detach_template_from_requests(self, template_id: UUID) -> int:
        """Null out workflow_template_id on every request that points at
        this template. Returns the number of rows affected so the caller
        can surface a count in audit / UI."""
        rows = await self._fetch_all(
            "UPDATE t_share_requests SET workflow_template_id = NULL WHERE workflow_template_id = $1 RETURNING id",
            (template_id,),
        )
        return len(rows)

    async def find_requests_using_template(self, template_id: UUID) -> list[dict]:
        return await self._fetch_all(
            "SELECT id, status FROM t_share_requests WHERE workflow_template_id = $1",
            (template_id,),
        )

    async def find_stuck_requests(self, tenant_id: int) -> list[dict]:
        """Submitted-or-later requests that have no workflow steps recorded.
        These are the requests the backfill endpoint targets — typically
        ones that were submitted before any active workflow template
        existed for their (sharing_type, data_classification)."""
        return await self._fetch_all(
            """
            SELECT r.* FROM t_share_requests r
            WHERE r.tenant_id = $1
              AND r.status NOT IN ('draft', 'cancelled', 'rejected', 'completed')
              AND NOT EXISTS (
                SELECT 1 FROM t_workflow_steps s WHERE s.request_id = r.id
              )
            """,
            (tenant_id,),
        )

    async def deactivate_others(self, tenant_id: int, sharing_type: str | None,
                                data_classification: str | None, exclude_id: UUID) -> None:
        if sharing_type is None:
            st_cond = "sharing_type IS NULL"
            args = [tenant_id, exclude_id]
        else:
            st_cond = "sharing_type = $3"
            args = [tenant_id, exclude_id, sharing_type]

        idx = len(args) + 1
        if data_classification is None:
            dc_cond = "data_classification IS NULL"
        else:
            dc_cond = f"data_classification = ${idx}"
            args.append(data_classification)

        await self._execute(
            f"""UPDATE t_workflow_templates SET is_active = FALSE
                WHERE tenant_id = $1 AND id != $2 AND {st_cond} AND {dc_cond} AND is_active = TRUE""",
            tuple(args),
        )

    # --- Workflow Steps (per-request) ---

    async def create_step(self, request_id: UUID, template_step_id: UUID | None, step_order: int,
                          step_type: str, name: str | None, assignee_role: str | None,
                          assignee_user_id: int | None, sla_deadline=None, status: str = "pending") -> dict:
        return await self._fetch_row(
            """INSERT INTO t_workflow_steps (request_id, template_step_id, step_order, step_type, name,
               assignee_role, assignee_user_id, sla_deadline, status)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *""",
            (request_id, template_step_id, step_order, step_type, name, assignee_role, assignee_user_id, sla_deadline, status),
        )

    async def find_steps_by_request(self, request_id: UUID) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_workflow_steps WHERE request_id = $1 ORDER BY step_order", (request_id,)
        )

    async def find_step(self, step_id: UUID) -> dict:
        return await self._fetch_row("SELECT * FROM t_workflow_steps WHERE id = $1", (step_id,))

    async def update_step(self, step_id: UUID, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        args.append(step_id)
        return await self._fetch_row(
            f"UPDATE t_workflow_steps SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

    async def find_overdue_steps(self) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_workflow_steps WHERE sla_deadline < CURRENT_TIMESTAMP AND status = 'pending' AND escalated_at IS NULL"
        )

    async def find_steps_awaiting_second_escalation(self) -> list[dict]:
        """Steps already breached (escalation_level = 1) and still pending —
        candidates for the BRD §2.3 Day-5 escalation."""
        return await self._fetch_all(
            "SELECT * FROM t_workflow_steps "
            "WHERE status = 'pending' AND escalation_level = 1 "
            "AND second_escalated_at IS NULL"
        )

    async def find_steps_awaiting_stall(self) -> list[dict]:
        """Steps already at level 2 — candidates for the Day-7 auto-cancel."""
        return await self._fetch_all(
            "SELECT * FROM t_workflow_steps "
            "WHERE status = 'pending' AND escalation_level = 2 "
            "AND stalled_at IS NULL"
        )
