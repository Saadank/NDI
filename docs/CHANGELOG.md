# Changelog

Commit history of the Data Sharing Platform, newest first. Each entry preserves
the original commit message under its short SHA so this doc is a stable
reference even if history is ever rewritten.

---

## `e598e09` — 2026-04-24 — feat: BRD compliance — conflict rules, delegation, SLA calendar, retention, audit export, platform-admin boundary

Implements BRD items 1, 2, 3, 4, 11, 12, 14, 17. One new migration
(`010_brd_compliance.sql`) groups every schema addition.

- **EC-01:** same-department receiver blocked at create and re-checked at submit.
- **§2.2 role-conflict resolution:** steps where the requester is the assignee,
  or where a DPO / Data-Owner would self-review, are auto-delegated to the
  first Org Admin and audited as `step.auto_delegated`.
- **§2.3 out-of-office delegation:** users can nominate a same-department
  teammate with same-or-higher seniority; approvals by a delegate record
  `delegated_from_user_id`. New UI under **Sidebar → System → My Profile**.
- **§4.3 Saudi business calendar:** SLA deadlines skip Fri/Sat and
  tenant-configured public holidays (new `t_business_holidays` table with
  admin CRUD endpoints).
- **§2.3 escalation ladder** in the SLA worker: Day-3 first breach → Day-5
  second escalation (notifies Org Admin) → Day-7 auto-cancel the request.
- **§3.7 retention:** per-tenant `retention_days` (30/60/90/180, default 90);
  48-hour pre-expiry notification handled by the expiry worker.
- **§2.2 EC-21 audit export:** CSV download endpoint, auto-classified
  Confidential when the export references personal data, Org Admin notified in
  that case, export is itself audited via `t_audit_exports`.
- **§2.1 platform-admin boundary:** Platform Admin blocked from request / file /
  audit content; new `/platform/metrics/tenants/{id}` endpoint returns metadata
  only. §1.3 storage and seat quotas enforced on upload and invitation
  respectively.

---

## `27c4bc9` — 2026-04-20 — feat: admin onboarding wizard, users page, and product entitlement enforcement

Build the end-to-end tenant onboarding journey and close three gaps found
during first live run.

- Platform admin: new **Onboard Company** wizard (create tenant, enable
  products, invite first org admin) with live progress log.
- Org admin: new **Users** page with inline invite + team members + pending
  invitations tables.
- Enforce tenant-product entitlement on all `/products/data-sharing/*` routes
  via a router-level dependency, and gate matching frontend nav entries by
  `GET /products/me`.
- Allow `platform_admin` to target a different tenant when creating an
  invitation so the first admin lands in the new tenant.
- Add `/accept-invitation` static page and backend route; point `FRONTEND_URL`
  at the backend which now serves it.
- Grant realm-management roles to the `datasharing-backend` Keycloak service
  account so it can create users via the admin API (fixes 403 during
  invitation accept).

---

## `905d8ca` — 2026-04-18 — OCI deployment hardening: blocker fixes + hardening

Drop-in replacements + new files to fix 6 blocker issues found in the OCI
deployment plan review and add production-ready hardening.

**Blockers fixed:**
- `nginx.conf`: cert paths `fullchain.pem` / `privkey.pem` (match certbot).
- `nginx.conf`: separate vhosts for app / api / auth with Keycloak upstream.
- `nginx.conf` + `docker-compose.prod.yml`: static frontend mounted at root.
- `docker-compose.prod.yml`: Keycloak now uses its own dedicated DB.
- `scripts/issue-certs.sh` + `renew-certs.sh`: webroot ACME (nginx stays up).
- `.github/workflows/deploy.yml`: single workflow replacing both conflicting
  ones.

**Hardening:**
- Log rotation, healthchecks, no public ports on internal services.
- `KC_HOSTNAME_STRICT*` tuned for Keycloak 24 + edge TLS.
- Redis password-protected.
- Security headers hardened (CSP, Permissions-Policy, HSTS preload).
- Rate limits + connection limits at nginx.
- New `backup.sh`: `mc mirror` for MinIO + separate KC DB dump + heartbeat.
- New `restore-drill.sh` for monthly DR drills.
- New `bootstrap-vm.sh`: idempotent VM setup (iptables, docker, mc, OCI CLI).
- Image tagging by git SHA for rollback via `workflow_dispatch`.
- Migrations run via `run --rm api alembic upgrade head` (no silent `|| true`).

**Files changed:**
- `docker-compose.prod.yml` (rewritten)
- `.env.prod.example` (added KC DB creds, Redis password, image vars)
- `nginx/nginx.conf` (rewritten)
- `nginx/nginx-bootstrap.conf` (new)
- `.github/workflows/deploy.yml` (rewritten)
- `backend/setup/db/00_init_keycloak_db.sql` (new)
- `scripts/bootstrap-vm.sh`, `backup.sh`, `restore-drill.sh`,
  `issue-certs.sh`, `renew-certs.sh`, `set-keycloak-db-password.sh`,
  `launch-vm-retry.sh` (new)

---

## `c5c9d50` — 2026-04-17 — fix: harden request validation and PDPL rules from test findings

- Enforce `DataClassification` enum and `Literal` types on share-request body.
- Require `min_length` for title, purpose, invitation fields.
- Use `EmailStr` for invitation and external-recipient emails.
- Whitelist file upload MIME types and require `mime_type`.
- Return 401 (`UnauthorizedException`) for invalid credentials.
- Require `legal_basis` for confidential / sensitive classifications.
- Cap workflow step SLA by classification (public=30, internal=14,
  confidential=7, sensitive=3).
- Add `pydantic[email]` and `email-validator` dependencies.

---

## `30ef2df` — 2026-04-17 — feat: add external recipient magic-link pickup portal

Deliver shared data to organisations that don't have a Platform account, via a
passwordless magic-link portal. The source tenant's workflow approves the
share; on final approval, a time-boxed token is minted and emailed to the
contact. The recipient accepts a DPA and downloads the artifacts through
ephemeral 120 s presigned MinIO URLs. Everything is audited on the source
tenant's side; tokens are revocable.

Structured-data shares materialize a CSV snapshot on approval (no live DB
access for non-customer recipients). Adds admin directory for DPOs / admins to
browse recipients, contacts, and active tokens.

Also fixes a pre-existing bug in `notification_repository.update_email_status`
where `$1` was used in two contexts with conflicting inferred types (varchar
vs text), causing every UPDATE to throw and emails to be resent every worker
tick.

---

## `9f3b262` — 2026-04-15 — Merge structured data sharing feature

_(Merge commit — no body.)_

---

## `3d53613` — 2026-04-15 — feat: add structured data sharing via DB connections

- New migration `008_ds_structured.sql`: adds `data_type`, `connection_id`,
  `selection_mode`, `selected_items`, `custom_sql` on `t_share_requests`.
- Requesters can now pick a connection, select tables / columns OR write a
  SELECT query, preview 100 rows, and submit — the full query runs at submit
  time and the CSV is attached via the existing files flow.
- New `/structured/preview` and `/structured/attach` endpoints.
- `/connections/browse` and `/schemas/{id}/browse` for requester access (no
  passwords exposed); schema introspected on demand.
- **Frontend:** Data Source toggle in New Request; schema tree or SQL editor;
  inline preview; request detail shows selection / SQL.

---

## `74e0a7a` — 2026-04-15 — feat: add file attachments to request creation and tenant2 seed data

- **Frontend:** add multi-file upload field to request form with Submit / Draft
  actions.
- **Backend:** add `seed_tenant2_data.py` for tenant2 Keycloak setup.
- **Gitignore:** exclude `.claude/` local settings.

---

## `0dc0028` — 2026-04-15 — fix: add sqlalchemy dependency and fix pool_size NameError in db connector

- Add `sqlalchemy[asyncio]` to `pyproject.toml` (was imported but missing).
- Store `pool_size` on `self` so `_create_engine` can reference it.

---

## `cdfd220` — 2026-04-15 — fix: use separate MinIO client for presigned URLs to fix signature mismatch

The presigned URL must be generated with `localhost:9000` as the endpoint (not
string-replaced after) so the S3 V4 signature matches the `Host` header the
browser sends. Region is set explicitly to avoid a network lookup from inside
Docker.

---

## `fa41ec5` — 2026-04-15 — feat: integrate file upload into request workflow with approver/receiver download

Files are now managed directly from the request detail view instead of
requiring manual UUID entry. Requesters can upload files during draft,
approvers can download before deciding, and receivers can download after
approval.

- Allow file uploads on draft requests (previously only submitted+).
- Add `GET /files/by-request/{request_id}` endpoint to list files per request.
- Add permission checks on download (must have access to parent request).
- Show attached files table with download / delete in request detail view.
- Inline file upload widget in request detail for writable statuses.
- Fix presigned URLs to use `localhost` instead of internal Docker hostname.
- Fix `docker-compose` env var interpolation with defaults and `env_file`.
- Fix 422 error display in frontend `api()` helper for validation errors.
- Add request dropdown in Files tab instead of manual UUID input.

---

## `78471e4` — 2026-04-14 — feat: add data owner per department with member management and routed approvals

- Each department group has a designated `data_owner_id`.
- Data owner can manage members (add / remove) of their own department.
- Workflow data-owner steps are routed to the specific department's data owner.
- Only the assigned data owner can approve (not any `data_owner`-role user).
- Data owners see **Groups** section to manage their department.
- Admin can set data owner via "Set as Data Owner" button in member list.
- Comprehensive seed data: 3 departments, 1 DPO, 3 data owners, 6 stewards.
- Group table shows Data Owner column with owner name.

---

## `ac00d3b` — 2026-04-13 — feat: add department groups, receiver selection, and sequential workflow visibility

- Add `t_groups` table for department-based access (Finance, HR, IT, etc.).
- Users belong to one group; requests track `requester_group_id` and
  `receiver_group_id`.
- Group CRUD API with member management (org_admin only).
- Replace raw `receiving_tenant_id` input with group dropdown in create
  request form.
- Sequential workflow: only step 1 starts as pending, rest are waiting.
- Each role sees requests only when it's their turn:
  - **DPO:** sees requests when DPO step is pending.
  - **Data owner:** sees requests only when data-owner step is pending.
  - **Receiver / any group member:** sees requests only after all workflow
    steps approved.
  - Everyone always sees their own created requests.
- Fix Keycloak seed to preserve user profile fields (email, name).
- Fix template editing FK constraint (`ON DELETE SET NULL`).

---

## `356ec0b` — 2026-04-13 — feat: improve workflow system — RBAC enforcement, template editing, one-active rule

- Restrict workflow template management to `org_admin` / `platform_admin` only
  (remove DPO).
- Enforce role-based approval: each role can only approve steps assigned to
  them.
- Add template edit (PUT), get (GET), and deactivate (DELETE) API endpoints.
- Enforce one active template per `sharing_type` + `data_classification`
  combo.
- Show deactivated templates in list so admins can reactivate them.
- Hide **Workflow Templates** sidebar section for non-admin users.
- Only show Approve / Reject / Request Changes buttons to the assigned role.
- Add `product_role` to login response for frontend role checks.
- Seed default workflow template (DPO Review + Data Owner Approval).

---

## `58796ef` — 2026-04-12 — feat: add role-based access control (RBAC) for data sharing product

Enforce per-role permissions across all data-sharing endpoints based on the
defined permission matrix. DPO sees all requests, requester sees only own,
receiver sees only received, `data_owner` sees only assigned. Connections /
schemas restricted to admins, workflows / users / invitations to admins + DPO.
Approval steps validated against `assignee_role`.

- Add `permissions.py` with centralised permission matrix.
- Resolve `product_role` from `t_user_product_roles` in `security.py`.
- Add `USER` platform role for non-admin users.
- Add filtered repo queries (`find_by_requester`, `find_assigned_to_role`).
- Enforce permission checks in all service layers.

---

## `38630bf` — 2026-04-11 — refactor: strip non-MVP modules, add frontend test UI

Remove DSA, Breaches, DSR, and Glossary — not in MVP scope. Add single-file
frontend (`frontend/index.html`) for testing the Data Sharing MVP endpoints.

**Deleted:**
- routers / services for: dsa, breaches, dsr, glossary.
- SQL migrations: `007_ds_dsa.sql`, `008_ds_pdpl.sql`.
- `t_glossary_entries` table from `003_ds_connections.sql`.
- `test_breaches.py`.

**Added:**
- `frontend/index.html` — MVP test UI (login, portal, requests, workflows,
  files, connections, notifications, audit).

Backend: 21 tests passing, CORS enabled.

---

## `1240a44` — 2026-04-11 — feat: initial platform build — Phase 1 complete

Data Management Platform with Data Sharing as first product module.

**Platform Core:**
- Multi-tenant auth via Keycloak (JWT + SAML / SSO ready).
- Tenant, user, invitation management.
- Product registry with per-tenant activation.
- Product portal screen (`GET /products/me`).
- Append-only audit trail.
- Role-based access: `platform_admin`, `org_admin` + 5 product roles.

**Data Sharing Product:**
- Share request lifecycle (draft → submit → approve → deliver).
- PDPL validation (legal basis, DPIA, data subjects).
- Configurable workflow templates with SLA deadlines.
- Approval / rejection / changes-requested flow.
- File upload to MinIO with SHA-256 integrity check.
- 60-second presigned download URLs.
- In-app + email notifications with queue.
- DB connections (6 DB types), schema discovery, business glossary.
- Data Sharing Agreements (DSA) with dual sign-off.
- Breach notification module (72 hr SDAIA clock).
- DSR log (30-day PDPL deadline tracking).

**Infrastructure:**
- Docker Compose (dev + prod) with Postgres, Redis, MinIO, Keycloak.
- Background workers: file expiry, SLA escalation, email delivery.
- GitHub Actions CI / CD (test + deploy).
- Nginx reverse proxy with rate limiting.
- 8 SQL migrations, 17 API routers, 23 passing tests.
