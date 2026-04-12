from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ShareRequestRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, request_number: str, title: str, purpose: str, legal_basis: str,
                     sharing_type: str, data_classification: str, personal_data_involved: bool,
                     estimated_data_subjects: int | None, data_subject_categories: list[str] | None,
                     source_description: str | None, requester_id: int, receiving_tenant_id: int | None,
                     created_by: int, dpia_confirmed: bool = False) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_share_requests
               (tenant_id, request_number, title, purpose, legal_basis, sharing_type, data_classification,
                personal_data_involved, estimated_data_subjects, data_subject_categories, source_description,
                requester_id, receiving_tenant_id, created_by, dpia_confirmed)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
               RETURNING *""",
            (tenant_id, request_number, title, purpose, legal_basis, sharing_type, data_classification,
             personal_data_involved, estimated_data_subjects, data_subject_categories, source_description,
             requester_id, receiving_tenant_id, created_by, dpia_confirmed),
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

    # --- Receiver: requests sent to their tenant ---

    async def find_by_receiving_tenant(self, receiving_tenant_id: int, status: str | None,
                                       page: int, limit: int) -> list[dict]:
        conditions = ["receiving_tenant_id = $1", "deleted_at IS NULL"]
        args: list = [receiving_tenant_id]
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

    async def count_by_receiving_tenant(self, receiving_tenant_id: int, status: str | None) -> int:
        conditions = ["receiving_tenant_id = $1", "deleted_at IS NULL"]
        args: list = [receiving_tenant_id]
        if status:
            conditions.append("status = $2")
            args.append(status)
        where = " AND ".join(conditions)
        return await self._fetch_value(f"SELECT COUNT(*) FROM t_share_requests WHERE {where}", tuple(args))

    # --- Data Owner: requests with workflow steps assigned to their role ---

    async def find_assigned_to_role(self, tenant_id: int, role: str, status: str | None,
                                    page: int, limit: int) -> list[dict]:
        conditions = ["r.tenant_id = $1", "r.deleted_at IS NULL",
                       "EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.assignee_role = $2)"]
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
                       "EXISTS (SELECT 1 FROM t_workflow_steps ws WHERE ws.request_id = r.id AND ws.assignee_role = $2)"]
        args: list = [tenant_id, role]
        if status:
            conditions.append("r.status = $3")
            args.append(status)
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
