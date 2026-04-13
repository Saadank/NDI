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
