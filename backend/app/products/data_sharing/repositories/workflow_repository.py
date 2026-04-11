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

    # --- Workflow Steps (per-request) ---

    async def create_step(self, request_id: UUID, template_step_id: UUID | None, step_order: int,
                          step_type: str, name: str | None, assignee_role: str | None,
                          assignee_user_id: int | None, sla_deadline=None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_workflow_steps (request_id, template_step_id, step_order, step_type, name,
               assignee_role, assignee_user_id, sla_deadline)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *""",
            (request_id, template_step_id, step_order, step_type, name, assignee_role, assignee_user_id, sla_deadline),
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
