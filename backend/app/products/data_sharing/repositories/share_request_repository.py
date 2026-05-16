from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ShareRequestRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, request_number: str, title: str, purpose: str, legal_basis: str,
                     sharing_type: str, data_classification: str, personal_data_involved: bool,
                     estimated_data_subjects: int | None, data_subject_categories: list[str] | None,
                     source_description: str | None, requester_id: int, receiving_tenant_id: int | None,
                     requester_group_id: int | None, receiver_group_id: int | None,
                     created_by: int, dpia_confirmed: bool = False,
                     data_type: str = "file", connection_id=None, selection_mode: str | None = None,
                     selected_items=None, custom_sql: str | None = None,
                     external_recipient_id: int | None = None, external_contact_id: int | None = None,
                     delivery_channel: str = "portal",
                     request_direction: str = "pull") -> dict:
        import json
        selected_items_json = json.dumps(selected_items) if selected_items is not None else None
        return await self._fetch_row(
            """INSERT INTO t_share_requests
               (tenant_id, request_number, title, purpose, legal_basis, sharing_type, data_classification,
                personal_data_involved, estimated_data_subjects, data_subject_categories, source_description,
                requester_id, receiving_tenant_id, requester_group_id, receiver_group_id, created_by, dpia_confirmed,
                data_type, connection_id, selection_mode, selected_items, custom_sql,
                external_recipient_id, external_contact_id, delivery_channel, request_direction)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
                       $18,$19,$20,$21::jsonb,$22,$23,$24,$25,$26)
               RETURNING *""",
            (tenant_id, request_number, title, purpose, legal_basis, sharing_type, data_classification,
             personal_data_involved, estimated_data_subjects, data_subject_categories, source_description,
             requester_id, receiving_tenant_id, requester_group_id, receiver_group_id, created_by, dpia_confirmed,
             data_type, connection_id, selection_mode, selected_items_json, custom_sql,
             external_recipient_id, external_contact_id, delivery_channel, request_direction),
        )

    async def find_by_id(self, request_id: UUID, tenant_id: int) -> dict:
        return await self._fetch_row(
            "SELECT * FROM t_share_requests WHERE id = $1 AND tenant_id = $2 AND deleted_at IS NULL",
            (request_id, tenant_id),
        )

    async def find_by_tenant(self, tenant_id: int, status: str | None, page: int, limit: int) -> list[dict]:
        conditions = ["tenant_id = $1", "deleted_at IS NULL"]
        args: list = [tenant_id]
        idx = 2
        if status:
            conditions.append(f"status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        return await self._fetch_all(
            f"SELECT * FROM t_share_requests WHERE {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_by_tenant(self, tenant_id: int, status: str | None) -> int:
        if status:
            return await self._fetch_value(
                "SELECT COUNT(*) FROM t_share_requests WHERE tenant_id = $1 AND status = $2 AND deleted_at IS NULL",
                (tenant_id, status),
            )
        return await self._fetch_value(
            "SELECT COUNT(*) FROM t_share_requests WHERE tenant_id = $1 AND deleted_at IS NULL", (tenant_id,)
        )

    async def update_status(self, request_id: UUID, status: str, updated_by: int | None = None) -> dict:
        return await self._fetch_row(
            """UPDATE t_share_requests SET status = $1, updated_at = CURRENT_TIMESTAMP, updated_by = $2
               WHERE id = $3 RETURNING *""",
            (status, updated_by, request_id),
        )

    async def update(self, request_id: UUID, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        set_clauses.append("version = version + 1")
        args.append(request_id)
        return await self._fetch_row(
            f"UPDATE t_share_requests SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

    # --- Requester: own requests only ---

    async def find_by_requester(self, tenant_id: int, requester_id: int, status: str | None,
                                page: int, limit: int) -> list[dict]:
        conditions = ["tenant_id = $1", "requester_id = $2", "deleted_at IS NULL"]
        args: list = [tenant_id, requester_id]
        idx = 3
        if status:
            conditions.append(f"status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        return await self._fetch_all(
            f"SELECT * FROM t_share_requests WHERE {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_by_requester(self, tenant_id: int, requester_id: int, status: str | None) -> int:
        conditions = ["tenant_id = $1", "requester_id = $2", "deleted_at IS NULL"]
        args: list = [tenant_id, requester_id]
        if status:
            conditions.append("status = $3")
            args.append(status)
        where = " AND ".join(conditions)
        return await self._fetch_value(f"SELECT COUNT(*) FROM t_share_requests WHERE {where}", tuple(args))

    # --- Receiver: requests sent to their tenant or group, only after workflow is fully approved ---

    async def find_by_receiver(self, tenant_id: int, group_id: int | None, status: str | None,
                               page: int, limit: int) -> list[dict]:
        # Match by receiving_tenant_id OR receiver_group_id
        receiver_conds = ["r.receiving_tenant_id = $1"]
        args: list = [tenant_id]
        idx = 2
        if group_id:
            receiver_conds.append(f"r.receiver_group_id = ${idx}")
            args.append(group_id)
            idx += 1
        # Only show when workflow is complete (no pending/waiting steps remain)
        workflow_done = "NOT EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.status IN ('pending', 'waiting'))"
        conditions = [f"({' OR '.join(receiver_conds)})", "r.deleted_at IS NULL", workflow_done]
        if status:
            conditions.append(f"r.status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        return await self._fetch_all(
            f"SELECT r.* FROM t_share_requests r WHERE {where} ORDER BY r.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_by_receiver(self, tenant_id: int, group_id: int | None, status: str | None) -> int:
        receiver_conds = ["r.receiving_tenant_id = $1"]
        args: list = [tenant_id]
        idx = 2
        if group_id:
            receiver_conds.append(f"r.receiver_group_id = ${idx}")
            args.append(group_id)
            idx += 1
        workflow_done = "NOT EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.status IN ('pending', 'waiting'))"
        conditions = [f"({' OR '.join(receiver_conds)})", "r.deleted_at IS NULL", workflow_done]
        if status:
            conditions.append(f"r.status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        return await self._fetch_value(f"SELECT COUNT(*) FROM t_share_requests r WHERE {where}", tuple(args))

    # --- Data Owner: only requests where their step is currently pending ---

    async def find_assigned_to_role(self, tenant_id: int, role: str, status: str | None,
                                    page: int, limit: int) -> list[dict]:
        conditions = ["r.tenant_id = $1", "r.deleted_at IS NULL",
                       "EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.assignee_role = $2 AND ws.status = 'pending')"]
        args: list = [tenant_id, role]
        idx = 3
        if status:
            conditions.append(f"r.status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        return await self._fetch_all(
            f"SELECT r.* FROM t_share_requests r WHERE {where} ORDER BY r.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_assigned_to_role(self, tenant_id: int, role: str, status: str | None) -> int:
        conditions = ["r.tenant_id = $1", "r.deleted_at IS NULL",
                       "EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.assignee_role = $2 AND ws.status = 'pending')"]
        args: list = [tenant_id, role]
        if status:
            conditions.append("r.status = $3")
            args.append(status)
        where = " AND ".join(conditions)
        return await self._fetch_value(f"SELECT COUNT(*) FROM t_share_requests r WHERE {where}", tuple(args))

    # --- Combined: own requests + group-received (workflow done) + role-pending ---

    async def find_for_user(self, tenant_id: int, user_id: int, group_id: int | None,
                            assigned_role: str | None, status: str | None,
                            page: int, limit: int) -> list[dict]:
        """Returns share_requests visible to a specific user.

        Visibility is the OR of:
          1. requests the user submitted (always visible)
          2. any pending step assigned specifically to this user — by
             `assignee_user_id`, regardless of the step's `assignee_role`
             (a single user can be assigned to steps with different
             roles on different requests).
          3. (optional, when assigned_role is set) pending steps with
             NO specific assignee but matching the user's role
             (e.g. DPO steps that any DPO can pick up).
          4. (optional, when group_id is set) requests fully delivered
             to the user's group.

        Each row also gets a `current_step` JSON aggregate so the
        frontend can bucket the inbox by step role instead of by
        sender/receiver group.
        """
        visibility = [
            "r.requester_id = $2",
            # NEW: any pending step assigned specifically to this user.
            "EXISTS (SELECT 1 FROM t_workflow_steps ws "
            "        WHERE ws.request_id = r.id AND ws.status = 'pending' "
            "          AND ws.assignee_user_id = $2)",
        ]
        args: list = [tenant_id, user_id]
        idx = 3
        if group_id:
            visibility.append(
                f"(r.receiver_group_id = ${idx} AND NOT EXISTS "
                f"(SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.status IN ('pending','waiting')))"
            )
            args.append(group_id)
            idx += 1
        if assigned_role:
            # Null-assignee fallback: a pending step with no specific
            # user assigned but matching this caller's role (typically
            # DPO steps that any DPO in the tenant can pick up).
            visibility.append(
                f"EXISTS (SELECT 1 FROM t_workflow_steps ws "
                f"        WHERE ws.request_id = r.id AND ws.status = 'pending' "
                f"          AND ws.assignee_user_id IS NULL "
                f"          AND ws.assignee_role = ${idx})"
            )
            args.append(assigned_role)
            idx += 1
        conditions = [f"r.tenant_id = $1", "r.deleted_at IS NULL", f"({' OR '.join(visibility)})"]
        if status:
            conditions.append(f"r.status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        # `current_step` annotation: the lowest-step-order pending step
        # on this request, packed as a JSON object the frontend can
        # destructure. NULL when the workflow is finished or stalled.
        select_current_step = (
            "(SELECT row_to_json(cs)::jsonb FROM "
            "  (SELECT ws.id, ws.step_order, ws.name, ws.assignee_role, "
            "          ws.assignee_user_id, ws.status "
            "   FROM t_workflow_steps ws "
            "   WHERE ws.request_id = r.id AND ws.status = 'pending' "
            "   ORDER BY ws.step_order LIMIT 1) cs) AS current_step"
        )
        return await self._fetch_all(
            f"SELECT DISTINCT r.*, {select_current_step} "
            f"FROM t_share_requests r WHERE {where} "
            f"ORDER BY r.created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_for_user(self, tenant_id: int, user_id: int, group_id: int | None,
                             assigned_role: str | None, status: str | None) -> int:
        visibility = [
            "r.requester_id = $2",
            "EXISTS (SELECT 1 FROM t_workflow_steps ws "
            "        WHERE ws.request_id = r.id AND ws.status = 'pending' "
            "          AND ws.assignee_user_id = $2)",
        ]
        args: list = [tenant_id, user_id]
        idx = 3
        if group_id:
            visibility.append(
                f"(r.receiver_group_id = ${idx} AND NOT EXISTS "
                f"(SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.status IN ('pending','waiting')))"
            )
            args.append(group_id)
            idx += 1
        if assigned_role:
            visibility.append(
                f"EXISTS (SELECT 1 FROM t_workflow_steps ws "
                f"        WHERE ws.request_id = r.id AND ws.status = 'pending' "
                f"          AND ws.assignee_user_id IS NULL "
                f"          AND ws.assignee_role = ${idx})"
            )
            args.append(assigned_role)
            idx += 1
        conditions = [f"r.tenant_id = $1", "r.deleted_at IS NULL", f"({' OR '.join(visibility)})"]
        if status:
            conditions.append(f"r.status = ${idx}")
            args.append(status)
            idx += 1
        where = " AND ".join(conditions)
        return await self._fetch_value(f"SELECT COUNT(*) FROM t_share_requests r WHERE {where}", tuple(args))

    async def next_request_number(self, tenant_id: int) -> str:
        from datetime import datetime
        year = datetime.utcnow().year
        count = await self._fetch_value(
            "SELECT COUNT(*) FROM t_share_requests WHERE tenant_id = $1 AND request_number LIKE $2",
            (tenant_id, f"DSP-{year}-%"),
        )
        # Include tenant_id in the number to guarantee uniqueness across tenants
        return f"DSP-{year}-T{tenant_id}-{count + 1:04d}"
