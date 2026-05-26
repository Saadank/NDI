# NDI Data Management Platform — Complete Documentation

> **Version:** 1.0 | **Last Updated:** May 2026 | **Environment:** Development

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Tech Stack](#2-tech-stack)
3. [System Architecture](#3-system-architecture)
4. [Services & Ports](#4-services--ports)
5. [Project Structure](#5-project-structure)
6. [Database Schema](#6-database-schema)
7. [API Endpoints](#7-api-endpoints)
8. [User Roles & Permissions](#8-user-roles--permissions)
9. [Background Workers](#9-background-workers)
10. [Products](#10-products)
11. [Key Features](#11-key-features)
12. [Configuration Reference](#12-configuration-reference)
13. [Dev Setup & Credentials](#13-dev-setup--credentials)
14. [Platform Statistics](#14-platform-statistics)

---

## 1. Executive Summary

**NDI Data Management Platform** is a multi-product SaaS portal for Saudi Arabian enterprises. It provides a governed, PDPL-compliant channel for data sharing between departments and organizations, and serves as a centralized hub for data governance, compliance, and data subject rights management.

The platform is built around four products:

| Product | Status | Purpose |
|---|---|---|
| **Data Sharing** | Live (Phase 1) | Governed file & structured data sharing |
| **Data Quality** | Planned (Phase 2) | Data profiling & quality monitoring |
| **NDMO Compliance** | Planned (Phase 2) | National Data Management Office compliance |
| **Data Subject Rights** | Planned (Phase 2) | PDPL rights request management |

### Core Architectural Principle — BRD §2.1 CRITICAL

> **Platform Admin (vendor) is a data processor, NOT a data controller.**
> They are explicitly blocked from viewing any request content, files, audit events, or any data payload.
> They manage infrastructure only: tenants, quotas, product enablement, and org-level metrics.

---

## 2. Tech Stack

| Component | Version | Purpose |
|---|---|---|
| **Python** | 3.12 | Backend language |
| **FastAPI** | Latest | REST API framework (async) |
| **PostgreSQL** | 15 | Primary relational database |
| **Redis** | 7 | Caching, rate limiting, idempotency |
| **MinIO** | Latest | S3-compatible object storage for files |
| **Keycloak** | 24.0 | Identity management & SSO (JWT) |
| **Docker / Docker Compose** | Latest | Service orchestration |
| **MailHog** | Latest | Email capture for development |
| **uv** | Latest | Python package manager |

---

## 3. System Architecture

```
                    ┌────────────────────────────────────────────────────┐
                    │                  NDI Platform                      │
                    │                                                    │
  Frontend ─────────┼──► FastAPI API  (port 8000)                       │
  (port 3000/3001)  │         │                                         │
                    │    ┌────┴─────────────────────┐                   │
                    │    │     Platform Core         │                   │
                    │    │  Auth / Users / Tenants   │                   │
                    │    │  Products / Groups /      │                   │
                    │    │  Invitations / Audit /    │                   │
                    │    │  Holidays / Metrics       │                   │
                    │    └────┬─────────────────────┘                   │
                    │         │                                          │
                    │    ┌────┴─────────────────────┐                   │
                    │    │    Products Layer         │                   │
                    │    │                           │                   │
                    │    │  ● Data Sharing (Live)    │                   │
                    │    │  ● Data Quality (Phase 2) │                   │
                    │    │  ● NDMO (Phase 2)         │                   │
                    │    │  ● DSR (Phase 2)          │                   │
                    │    └────┬─────────────────────┘                   │
                    │         │                                          │
                    │  ┌──────┼──────────────────────────────────────┐  │
                    │  ▼      ▼           ▼          ▼        ▼      │  │
                    │ PostgreSQL  Redis   MinIO   Keycloak   SMTP    │  │
                    │  (port 5433)(6380) (9000)   (8080)   (1025)   │  │
                    └──────────────────────────────────────────────────┘
                                           │
                       ┌───────────────────┘
                       │   Background Workers (separate container)
                       │
                       │  ┌─────────────────────────────────────┐
                       │  │  Expiry Worker      (every 60 min)  │
                       │  │  SLA Worker         (every 30 min)  │
                       │  │  Notification Worker (every 5 min)  │
                       └──└─────────────────────────────────────┘

Public Pickup Portal (no auth):
  External recipients ──► /api/v1/pickup/{token}
                           Rate limited: 30 req/min
```

### Data Flow — Share Request Lifecycle

```
  Requester                Platform                    Data Owner / DPO
     │                        │                               │
     │── Create Draft ────────►│                               │
     │── Attach Files ─────────►│ (MinIO)                       │
     │── Submit Request ───────►│                               │
     │                        │──── Trigger Workflow ──────────►│
     │                        │                          Approve/Reject
     │◄── Notify ─────────────│◄──── Decision ─────────────────│
     │                        │                               │
     │                   [Approved]                           │
     │                        │                               │
  External Recipient ◄── Magic-link email                     │
     │── Accept DPA ──────────►│                               │
     │── Download Files ───────►│ (MinIO presigned URL)         │
```

---

## 4. Services & Ports

| Service | Image | Host Port | Container Port | Purpose |
|---|---|---|---|---|
| **API** | Custom (Dockerfile) | 8000 | 8000 | FastAPI backend |
| **Worker** | Custom (Dockerfile.worker) | — | — | Background jobs |
| **Keycloak** | quay.io/keycloak/keycloak:24.0 | 8080 | 8080 | Identity & SSO |
| **PostgreSQL** | postgres:15-alpine | 5433 | 5432 | Main database |
| **Redis** | redis:7-alpine | 6380 | 6379 | Cache & queues |
| **MinIO** | minio/minio:latest | 9000 | 9000 | File storage API |
| **MinIO Console** | minio/minio:latest | 9001 | 9001 | Storage web UI |
| **MailHog SMTP** | mailhog/mailhog:latest | 1025 | 1025 | Email capture |
| **MailHog UI** | mailhog/mailhog:latest | 8025 | 8025 | Email web UI |

---

## 5. Project Structure

```
NDI-dev/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py             # All settings (env-driven)
│   │   │   ├── database.py           # PostgreSQL async pool
│   │   │   ├── security.py           # JWT decode, get_current_user
│   │   │   └── tenant_context.py     # Tenant isolation helpers
│   │   │
│   │   ├── platform/                 # Platform Core module
│   │   │   ├── routers/
│   │   │   │   ├── auth.py           # Login / refresh / logout
│   │   │   │   ├── users.py          # User CRUD & delegation
│   │   │   │   ├── tenants.py        # Tenant management
│   │   │   │   ├── products.py       # Product catalogue & entitlements
│   │   │   │   ├── groups.py         # Departments
│   │   │   │   ├── invitations.py    # User invitations
│   │   │   │   ├── audit.py          # Audit log & export
│   │   │   │   ├── holidays.py       # Business calendar
│   │   │   │   └── metrics.py        # Org-level metrics
│   │   │   ├── services/             # Business logic
│   │   │   ├── repositories/         # DB access layer
│   │   │   └── enums/
│   │   │       └── platform_role.py  # PLATFORM_ADMIN | ORG_ADMIN | USER
│   │   │
│   │   ├── products/
│   │   │   ├── data_sharing/         # Live — Phase 1
│   │   │   │   ├── routers/
│   │   │   │   │   ├── share_requests.py
│   │   │   │   │   ├── approvals.py
│   │   │   │   │   ├── files.py
│   │   │   │   │   ├── pickup.py        # Public portal
│   │   │   │   │   ├── connections.py
│   │   │   │   │   ├── structured.py
│   │   │   │   │   ├── schemas.py
│   │   │   │   │   ├── workflows.py
│   │   │   │   │   ├── external_recipients.py
│   │   │   │   │   └── notifications.py
│   │   │   │   ├── services/
│   │   │   │   ├── repositories/
│   │   │   │   ├── workers/
│   │   │   │   │   ├── expiry_worker.py
│   │   │   │   │   ├── sla_worker.py
│   │   │   │   │   └── notification_worker.py
│   │   │   │   ├── enums/
│   │   │   │   │   ├── sharing_role.py
│   │   │   │   │   ├── data_classification.py
│   │   │   │   │   ├── legal_basis.py
│   │   │   │   │   └── request_status.py
│   │   │   │   ├── permissions.py
│   │   │   │   └── dependencies.py
│   │   │   │
│   │   │   └── data_quality/         # Placeholder — Phase 2
│   │   │       └── README.md
│   │   │
│   │   ├── gateways/
│   │   │   ├── keycloak_gateway.py   # Auth & user management
│   │   │   ├── object_store_gateway.py # MinIO uploads/downloads
│   │   │   ├── email_gateway.py      # SMTP email sender
│   │   │   ├── cache_gateway.py      # Redis wrapper
│   │   │   └── db_connector_gateway.py # External DB connections
│   │   │
│   │   ├── structures/
│   │   │   ├── auth_user.py          # AuthUser model (from JWT)
│   │   │   ├── list_response.py      # Paginated response wrapper
│   │   │   └── postgresql_async_repository.py # Base repo class
│   │   │
│   │   ├── utils/
│   │   │   ├── exceptions.py         # HTTP exception classes
│   │   │   ├── pagination.py         # Page/limit helpers
│   │   │   ├── business_calendar.py  # Saudi working day calculator
│   │   │   ├── rate_limit.py         # Redis sliding window
│   │   │   ├── request_info.py       # IP/user-agent extraction
│   │   │   └── timezone.py           # Timezone helpers
│   │   │
│   │   └── main.py                   # FastAPI app, middleware, router registration
│   │
│   ├── setup/
│   │   ├── db/                       # SQL migration files (001–010)
│   │   └── keycloak/
│   │       ├── setup_realm.py        # Create Keycloak realm (run once)
│   │       ├── seed_test_data.py     # Seed dev users & departments
│   │       └── seed_tenant2_data.py  # Seed second tenant
│   │
│   ├── tests/
│   ├── Dockerfile                    # API container
│   ├── Dockerfile.worker             # Worker container
│   └── pyproject.toml
│
├── frontend/                         # Static HTML pages
│   ├── index.html                    # Landing page
│   ├── pickup.html                   # External file download portal
│   └── accept-invitation.html        # Invitation acceptance page
│
├── nginx/                            # Reverse proxy config
├── scripts/                          # Dev & ops utilities
├── docker-compose.dev.yml
├── docker-compose.prod.yml
└── .env.dev
```

---

## 6. Database Schema

### Platform Core Tables

#### `t_tenants` — Organizations
| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| name | TEXT | Organization name (English) |
| name_ar | TEXT | Organization name (Arabic) |
| slug | TEXT UNIQUE | URL-safe identifier |
| tenant_type | TEXT | e.g. `internal_org`, `government` |
| dpo_name | TEXT | Data Protection Officer name |
| dpo_email | TEXT | Data Protection Officer email |
| retention_days | INT | File retention: 30, 60, 90, or 180 days |
| storage_limit_gb | INT | Max storage quota |
| seat_limit | INT | Max user count |
| is_active | BOOLEAN | |
| created_at / updated_at / deleted_at | TIMESTAMP | Lifecycle |

#### `t_users` — Platform users
| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | |
| tenant_id | FK → t_tenants | |
| keycloak_id | UUID UNIQUE | Keycloak subject ID |
| email | TEXT | |
| first_name / last_name | TEXT | |
| platform_role | TEXT | `platform_admin` \| `org_admin` \| `user` |
| group_id | FK → t_groups | Department membership |
| is_active | BOOLEAN | |
| delegation_to_user_id | FK → t_users | Out-of-office delegate |
| delegation_start / end | TIMESTAMP | Delegation window |
| delegation_reason | TEXT | |
| deleted_at | TIMESTAMP | Soft delete |

#### `t_products` — Product catalogue (seeded)
| Column | Description |
|---|---|
| id, slug, name, name_ar | Identity |
| description | What the product does |
| is_active | Globally available |
| sort_order | Display order |

**Seeded products:**
- `data_sharing` — Data Sharing Platform
- `data_quality` — Data Quality Profiling
- `ndmo` — NDMO Compliance
- `dsr` — Data Subject Rights

#### `t_tenant_products` — Product entitlements per tenant
| Column | Description |
|---|---|
| tenant_id + product_id | Unique per pair |
| enabled | Is the product active |
| enabled_by / disabled_by | Audit trail |
| enabled_at / disabled_at | Timestamps |

#### `t_user_product_roles` — Role per user per product
| Column | Description |
|---|---|
| user_id + product_id | Unique per pair |
| role | Product-specific role string (e.g. `requester`, `dpo`) |
| assigned_by | FK → t_users |

#### `t_invitations` — Pending invitations
| Column | Description |
|---|---|
| email, role, product_slug, product_role | Invitation details |
| token | Unique acceptance token |
| status | `pending` \| `accepted` |
| invited_by | FK → t_users |
| expires_at | Auto-expire |

#### `t_platform_admins` — Vendor admin accounts
Separate from `t_users` — vendor staff who manage infrastructure only.

---

### Audit Tables

#### `t_audit_events` — Immutable audit log
| Column | Type | Description |
|---|---|---|
| id | UUID PK | |
| tenant_id | FK | |
| request_id | FK (nullable) | Related request if any |
| actor_id | FK → t_users | Who did it |
| actor_ip | INET | IP address |
| actor_user_agent | TEXT | Browser/client info (BRD §8.1) |
| action_type | TEXT | e.g. `request.submitted`, `file.expired_deleted` |
| resource_type | TEXT | e.g. `share_request`, `file` |
| resource_id | TEXT | ID of affected resource |
| before_state | JSONB | State before action |
| after_state | JSONB | State after action |
| metadata | JSONB | Extra context |
| created_at | TIMESTAMP | Immutable |

#### `t_audit_exports` — Log of every audit export (EC-21)
| Column | Description |
|---|---|
| requested_by | Who exported |
| format | Export format |
| filters | JSONB of applied filters |
| row_count | How many records exported |
| contains_personal_data | Boolean flag |
| classification | `internal` \| `confidential` \| `restricted` |

---

### Data Sharing Tables

#### `t_share_requests` — Core data sharing entity
| Column | Type | Description |
|---|---|---|
| id | UUID PK | |
| request_number | TEXT UNIQUE | Human-readable (e.g. DS-2026-001) |
| tenant_id | FK | |
| title | TEXT | |
| purpose | TEXT | |
| legal_basis | TEXT | PDPL legal basis |
| sharing_type | TEXT | `internal` \| `external` |
| data_classification | TEXT | `public` \| `internal` \| `confidential` \| `restricted` |
| personal_data_involved | BOOLEAN | |
| estimated_data_subjects | INT | |
| data_subject_categories | TEXT[] | |
| requester_id | FK → t_users | |
| requester_group_id | FK → t_groups | |
| receiving_tenant_id | FK → t_tenants | Internal shares |
| external_recipient_id | FK → t_external_recipients | External shares |
| external_contact_id | FK → t_recipient_contacts | |
| delivery_channel | TEXT | `portal` \| `email` \| `api` |
| data_type | TEXT | `file` \| `structured` |
| connection_id | FK | Structured data source |
| selection_mode | TEXT | `tables` \| `query` |
| selected_items | JSONB | `[{schema, table, columns}]` |
| custom_sql | TEXT | Custom SQL query |
| workflow_template_id | FK | |
| status | TEXT | `draft` → `submitted` → `approved`/`rejected` → `completed`/`cancelled` |
| expiry_at | TIMESTAMP | |
| dpia_confirmed | BOOLEAN | Data Protection Impact Assessment |
| created_at / updated_at / deleted_at | TIMESTAMP | |

#### `t_workflow_templates` — Reusable approval chains
| Column | Description |
|---|---|
| name | Template name |
| sharing_type | Optional filter (internal/external) |
| data_classification | Optional filter |
| is_active | |
| version | Template versioning |

#### `t_template_steps` — Steps in a template
| Column | Description |
|---|---|
| step_order | Sequence number |
| step_type | Type of step |
| name | Step label |
| assignee_role | `requester` \| `data_owner` \| `dpo` \| `source` \| `receiver` |
| execution_mode | `sequential` \| `parallel` |
| sla_days | Days to complete (default: 3) |
| condition_expr | Optional conditional logic |

#### `t_workflow_steps` — Live approval steps on a request
| Column | Description |
|---|---|
| step_order, assignee_role, assignee_user_id | Who should act |
| status | `pending` \| `approved` \| `rejected` \| `changes_requested` \| `completed` |
| decision, comment | Outcome details |
| sla_deadline | When SLA expires |
| escalation_level | 0–3 (triggers auto-cancel at 3) |
| escalated_at / second_escalated_at / stalled_at | Escalation timestamps |
| delegated_from_user_id | Original assignee (if delegated) |

#### `t_files` — Files stored in MinIO
| Column | Description |
|---|---|
| storage_key | Unique MinIO path |
| file_size_bytes | Size |
| sha256_hash | Integrity check |
| status | `pending_upload` \| `uploaded` \| `deleted` |
| expires_at | Auto-delete date |
| pre_expiry_notified_at | 48h warning sent flag |
| deleted_at / deletion_reason | Soft delete |

#### `t_connections` — External database connections
| Column | Description |
|---|---|
| db_type | `postgres`, `mysql`, `oracle`, etc. |
| host, port, database | Connection details |
| username, password_encrypted | Credentials (encrypted at rest) |
| status | `active` |

#### `t_schemas` — Cached DB schema introspection
| Column | Description |
|---|---|
| connection_id | FK |
| schema_data | JSONB of tables, columns, types |

#### `t_external_recipients` — Non-tenant organizations
| Column | Description |
|---|---|
| org_name | Organization name |
| notes | Notes |
| dpa_required | Whether DPA must be signed |
| is_active | |

#### `t_recipient_contacts` — Email contacts at external orgs
| Column | Description |
|---|---|
| recipient_id | FK → t_external_recipients |
| email, name, phone | Contact details |
| email_verified_at | Verification timestamp |

#### `t_pickup_tokens` — Magic-link download tokens
| Column | Description |
|---|---|
| token_hash | SHA256 of token (never stored in plain) |
| expires_at | 72 hours default |
| max_downloads | Default 10 |
| download_count | Usage counter |
| dpa_accepted_at | When DPA was accepted |
| dpa_ip | IP at acceptance (forensic, BRD §8.1) |
| dpa_user_agent | Browser at acceptance (forensic) |
| revoked_at / revoked_by / revoke_reason | Revocation |

#### `t_notifications` — In-app notifications
| Column | Description |
|---|---|
| user_id | Recipient |
| type, title, body | Content |
| request_id | Related request (optional) |
| is_read, read_at | Read state |

#### `t_email_queue` — Outbound email queue
| Column | Description |
|---|---|
| to_email, subject, html_body | Email content |
| status | `pending` \| `sent` \| `failed` |
| attempts | Retry counter |
| last_error | Last failure reason |

#### `t_groups` — Departments within a tenant
| Column | Description |
|---|---|
| name, name_ar | Department name |
| slug | URL-safe identifier (unique per tenant) |
| data_owner_id | Designated data steward user |
| is_active | |

#### `t_business_holidays` — Saudi public holidays per tenant
| Column | Description |
|---|---|
| holiday_date | Date of holiday |
| name, name_ar | Holiday name |
| created_by | Who added it |

---

## 7. API Endpoints

> **Base URL:** `http://localhost:8000`
> All endpoints require `Authorization: Bearer <token>` except `/api/v1/pickup/*`

### Platform: Authentication
`/api/v1/platform/auth`

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/login` | Anyone | Login with email + password |
| POST | `/refresh` | Authenticated | Get new access token |
| POST | `/logout` | Authenticated | Invalidate refresh token |

### Platform: Users
`/api/v1/platform/users`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Org Admin, DPO | List users (page, limit) |
| GET | `/me` | All | Get own profile |
| GET | `/{user_id}` | Org Admin, DPO | Get user by ID |
| POST | `/me/delegation` | All | Set out-of-office delegate |
| DELETE | `/me/delegation` | All | Remove delegation |
| PUT | `/{user_id}/group` | Org Admin | Assign user to department |
| POST | `/{user_id}/deactivate` | Org Admin | Deactivate user account |

### Platform: Tenants
`/api/v1/platform/tenants`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Platform Admin | List all tenants |
| POST | `/` | Platform Admin | Create new tenant |
| GET | `/{tenant_id}` | Platform Admin | Get tenant details |
| PUT | `/{tenant_id}/retention-policy` | Platform Admin | Set retention (30/60/90/180 days) |
| PUT | `/{tenant_id}/quotas` | Platform Admin | Set storage & seat limits |

### Platform: Products
`/api/v1/platform/products`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | All | Full product catalogue |
| GET | `/me` | All | Products enabled for my tenant |
| GET | `/tenants/{tenant_id}` | Platform Admin | Products for a specific tenant |
| POST | `/tenants/{tenant_id}` | Platform Admin | Enable product for tenant |
| DELETE | `/tenants/{tenant_id}/{slug}` | Platform Admin | Disable product |
| POST | `/users/{user_id}/product-roles` | Org Admin | Assign product role to user |

### Platform: Groups (Departments)
`/api/v1/platform/groups`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | All | List departments |
| POST | `/` | Org Admin | Create department |
| PUT | `/{group_id}` | Org Admin | Update department |
| DELETE | `/{group_id}` | Org Admin | Deactivate department |
| PUT | `/{group_id}/data-owner` | Org Admin | Assign data owner |
| GET | `/{group_id}/members` | Org Admin, DPO | List members |
| POST | `/{group_id}/members` | Org Admin | Add member |
| DELETE | `/{group_id}/members/{user_id}` | Org Admin | Remove member |

### Platform: Invitations
`/api/v1/platform/invitations`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Org Admin | List invitations |
| POST | `/` | Org Admin | Send invitation (role + product role) |
| POST | `/accept` | Anyone (via email link) | Accept invitation & register |

### Platform: Audit
`/api/v1/platform/audit`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Org Admin, DPO | List audit events (filters: request_id, actor_id, action_type) |
| GET | `/export` | Org Admin, DPO | Export audit trail as CSV (auto-classifies if personal data) |

### Platform: Holidays
`/api/v1/platform/holidays`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | All | List business holidays (filter by year) |
| POST | `/` | Org Admin | Add / update holiday |
| DELETE | `/{holiday_id}` | Org Admin | Delete holiday |

### Platform: Metrics
`/api/v1/platform/metrics`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}` | Platform Admin | Org metrics: user count, storage used, request counts, quotas |

---

### Data Sharing: Share Requests
`/api/v1/products/data-sharing/requests`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Role-filtered | List requests (see visibility rules) |
| POST | `/` | Requester, Data Owner, DPO, Org Admin | Create draft request |
| GET | `/{request_id}` | Role-filtered | Get full request details |
| POST | `/{request_id}/submit` | Request creator | Submit to trigger workflow |
| POST | `/{request_id}/cancel` | Request creator, Org Admin | Cancel request |

### Data Sharing: Approvals
`/api/v1/products/data-sharing/requests/{request_id}/steps`

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/{step_id}/approve` | Assignee, delegate, Org Admin | Approve step |
| POST | `/{step_id}/reject` | Assignee, delegate, Org Admin | Reject step (comment required) |
| POST | `/{step_id}/request-changes` | Assignee | Request changes (comment required) |

### Data Sharing: Files
`/api/v1/products/data-sharing/files`

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/initiate` | Requester+ | Initiate upload (returns upload token) |
| GET | `/by-request/{request_id}` | Role-filtered | List files on request |
| PUT | `/{file_id}/upload` | Uploader | Upload file (multipart, max 5 GB) |
| GET | `/{file_id}/download-url` | Role-filtered | Get presigned MinIO URL (120s TTL) |
| DELETE | `/{file_id}` | Uploader, Org Admin | Soft-delete file |

### Data Sharing: Connections
`/api/v1/products/data-sharing/connections`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Org Admin | List connections with credentials |
| GET | `/browse` | Requester+ | List connections without passwords |
| POST | `/` | Org Admin | Register DB connection |
| POST | `/{connection_id}/test` | Org Admin | Test connection health |
| PUT | `/{connection_id}` | Org Admin | Update connection |

### Data Sharing: Structured Data
`/api/v1/products/data-sharing/structured`

| Method | Path | Who | Description |
|---|---|---|---|
| POST | `/preview` | Requester+ | Preview query results (limited rows) |
| POST | `/attach` | Requester+ | Attach structured export to request |

### Data Sharing: Schemas
`/api/v1/products/data-sharing/schemas`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/{connection_id}` | Org Admin | Get cached schema |
| GET | `/{connection_id}/browse` | Requester+ | Browse live schema (read-only) |

### Data Sharing: Workflow Templates
`/api/v1/products/data-sharing/workflows`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/templates` | Org Admin, DPO | List templates |
| POST | `/templates` | Org Admin | Create template |
| GET | `/templates/{id}` | Org Admin, DPO | Get template with steps |
| PUT | `/templates/{id}` | Org Admin | Update template |
| DELETE | `/templates/{id}` | Org Admin | Delete template |

### Data Sharing: External Recipients
`/api/v1/products/data-sharing/external-recipients`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | Org Admin, DPO | List recipients (search, page, limit) |
| GET | `/{id}` | Org Admin, DPO | Get recipient details |
| PATCH | `/{id}` | Org Admin, DPO | Update recipient info |
| POST | `/{id}/contacts` | Org Admin, DPO | Add contact email |
| PATCH | `/{id}/contacts/{contact_id}` | Org Admin, DPO | Update contact |
| DELETE | `/{id}/contacts/{contact_id}` | Org Admin, DPO | Remove contact |
| POST | `/{id}/tokens` | Org Admin, DPO | Generate magic-link download token |
| POST | `/{id}/tokens/{token_id}/revoke` | Org Admin, DPO | Revoke token |

### Data Sharing: Notifications
`/api/v1/products/data-sharing/notifications`

| Method | Path | Who | Description |
|---|---|---|---|
| GET | `/` | All | List my notifications (unread_only filter) |
| POST | `/{id}/read` | All | Mark notification as read |

### Pickup Portal (Public — No Auth Required)
`/api/v1/pickup`

> Rate-limited: 30 requests/minute per token prefix

| Method | Path | Description |
|---|---|---|
| GET | `/{token}` | Get request summary & file list (if DPA accepted) |
| POST | `/{token}/accept-dpa` | Accept Data Processing Agreement to unlock downloads |
| GET | `/{token}/files/{file_id}/download` | Download file (redirect to presigned MinIO URL) |

---

## 8. User Roles & Permissions

### Platform Roles

#### Platform Admin (Vendor)
- **Who:** NDI vendor staff
- **Scope:** Cross-tenant, infrastructure only
- **Can:**
  - Create and manage tenants
  - Set storage quotas and seat limits
  - Enable / disable products for tenants
  - View org-level metrics (counts, storage usage)
- **Cannot (BRD §2.1 CRITICAL):**
  - View any share requests or file content
  - View audit events (contain personal data)
  - Approve workflow steps
  - Access any data-controller content

#### Org Admin (Customer IT Admin)
- **Who:** Customer's IT administrator
- **Scope:** Their own tenant
- **Can:**
  - Manage users (invite, deactivate, assign to groups)
  - Manage departments (groups)
  - Configure workflow templates
  - Register DB connections
  - View ALL requests in their tenant
  - Approve any workflow step
  - View full audit log
  - Manage external recipients & pickup tokens
  - Set business holidays

#### User (Base)
- **Who:** Any platform user
- **Scope:** Defined by product role
- **Capabilities:** Determined entirely by their Data Sharing product role

---

### Data Sharing Product Roles

#### Requester
- Create and submit share requests
- Upload / delete files on own requests
- View own requests only
- Browse DB connections and schemas (read-only, no passwords)

#### Data Owner
- Approve workflow steps at the "data owner review" stage
- View requests that have a step assigned to their role
- Steward of their department's data

#### DPO (Data Protection Officer)
- View ALL requests in the tenant
- Approve any DPO-assigned workflow step
- View full audit log and export it
- Manage external recipients and pickup tokens
- Create and manage workflow templates
- Full visibility equal to Org Admin for governance tasks

#### Source
- View requests where they are the designated source
- Upload and manage source data files

#### Receiver
- View requests sent to their group or tenant
- Approve at the "receiver approval" workflow step
- Download files from approved requests they receive

---

### Permissions Matrix

| Action | Platform Admin | Org Admin | DPO | Data Owner | Requester | Receiver |
|---|---|---|---|---|---|---|
| View own requests | ✗ | ✓ | ✓ | ✓ (assigned) | ✓ (own) | ✓ (received) |
| View all requests | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Create request | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Approve step | ✗ | ✓ | ✓ (DPO steps) | ✓ (DO steps) | ✗ | ✓ (RCV steps) |
| View audit log | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Export audit | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Manage users | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Manage workflows | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Manage connections | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Browse connections | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Manage recipients | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Create tenant | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Set quotas | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| View org metrics | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Enable products | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |

---

## 9. Background Workers

All workers run in the **`worker` container** on configurable intervals. Each worker is independent and continues running after errors.

### Expiry Worker — Runs every 60 minutes

Manages file lifecycle per **BRD §3.7**.

**Step 1 — Pre-expiry warning (T − 48h):**
1. Query files expiring within 48 hours where `pre_expiry_notified_at IS NULL`
2. Create in-app notification for uploader and requester: `file_pre_expiry`
3. Queue warning email
4. Mark file: `pre_expiry_notified_at = NOW()`
5. Audit log: `file.pre_expiry_notified`

**Step 2 — Delete expired files:**
1. Query files where `expires_at < NOW()` and `status = 'uploaded'`
2. Delete bytes from MinIO (S3)
3. Soft-delete DB row: `deleted_at = NOW()`, `deletion_reason = 'expired'`
4. File metadata and audit trail are **retained forever**
5. Audit log: `file.expired_deleted`
6. Redis cache used for idempotency (`dsplatform:expiry_processed` set)

---

### SLA Escalation Worker — Runs every 30 minutes

Implements the escalation ladder per **BRD §2.3, EC-05**.
Business days use the **Saudi calendar** (Fri/Sat weekends + tenant holidays).

```
Step Submitted
      │
      │ SLA deadline passed (Day 3)
      ▼
  Level 1 — Notify assignee + Org Admin
      │
      │ +2 business days (Day 5)
      ▼
  Level 2 — Notify Org Admin to reassign
      │
      │ +2 business days (Day 7)
      ▼
  Level 3 — AUTO-CANCEL request
             Notify all stakeholders
```

| Level | Trigger | Action | DB Field |
|---|---|---|---|
| 0 → 1 | SLA deadline passed | Notify assignee + Org Admin | `escalated_at` |
| 1 → 2 | +2 business days | Notify Org Admin to reassign | `second_escalated_at` |
| 2 → 3 | +2 more business days | **Auto-cancel entire request** | `stalled_at` |

---

### Notification Worker — Runs every 5 minutes

Processes the `t_email_queue` table:

1. Query all rows where `status = 'pending'`
2. For each email:
   - Send HTML email via SMTP (`EmailGateway`)
   - **Success:** Set `status = 'sent'`, record `sent_at`
   - **Failure:** Increment `attempts`, store `last_error`
   - After 2 failures: Set `status = 'failed'` (give up)
3. Log results

---

## 10. Products

### Product 1: Data Sharing Platform ✅ Live (Phase 1)

**Slug:** `data_sharing`
**Arabic:** منصة مشاركة البيانات

The core product of the platform. Enables governed, audited sharing of data (files or structured DB exports) between departments within an organization or with external recipients.

**Key capabilities:**
- **File sharing** — Upload files (up to 5 GB), attach to request, deliver via portal/email/API
- **Structured data sharing** — Connect to external databases, select tables/columns or write SQL, export as CSV
- **Approval workflows** — Template-based multi-step approval chains with SLA tracking
- **External delivery** — Magic-link tokens for non-platform organizations (72h TTL, 10 downloads)
- **DPA enforcement** — External recipients must accept Data Processing Agreement before downloading
- **File retention** — Auto-expiry (30–180 days) with 48h warning and full audit trail
- **PDPL compliance** — Personal data flagging, legal basis tracking, DPA acceptance logging

---

### Product 2: Data Quality Profiling 🔜 Planned (Phase 2)

**Slug:** `data_quality`
**Arabic:** جودة البيانات
**Description:** Profile, measure, and monitor data quality across your data sources.

**Intended capabilities (not yet implemented):**
- Connect to data sources (databases, files, APIs)
- Automatically profile datasets: completeness, uniqueness, validity, consistency
- Set data quality rules and thresholds
- Monitor quality metrics over time with dashboards
- Alert on quality degradation
- Generate data quality reports for DPO review
- NDMO-aligned quality dimensions (BRD §5.x)

**Current status:** Module skeleton exists (`app/products/data_quality/`). No routers, services, or DB tables implemented. Registered in product catalogue. Awaiting Phase 2 development.

---

### Product 3: NDMO Compliance 🔜 Planned (Phase 2)

**Slug:** `ndmo`
**Arabic:** امتثال NDMO
**Description:** Manage compliance with NDMO data governance framework requirements.

**Intended capabilities (not yet implemented):**
- Track compliance with Saudi Arabia's National Data Management Office framework
- Maintain a data asset inventory (data catalog)
- Map data assets to NDMO classification levels
- Manage data governance policies and procedures
- Track NDMO audit findings and remediation
- Generate NDMO compliance reports
- Monitor data governance maturity scores

**Current status:** Registered in product catalogue only. No code implementation. Awaiting Phase 2 development.

---

### Product 4: Data Subject Rights (DSR) 🔜 Planned (Phase 2)

**Slug:** `dsr`
**Arabic:** حقوق أصحاب البيانات
**Description:** Receive, track, and respond to data subject rights requests within PDPL deadlines.

**Intended capabilities (not yet implemented):**
- Receive rights requests from data subjects:
  - Right to Access (Article 4)
  - Right to Correction (Article 5)
  - Right to Deletion (Article 6)
  - Right to Restriction (Article 7)
  - Right to Data Portability (Article 8)
  - Right to Object (Article 9)
- Auto-calculate PDPL deadlines (30-day response window)
- Route requests to responsible DPO or department
- Track fulfillment status with escalation
- Generate response letters
- Maintain DSR audit trail for NDMO inspection
- Dashboard for open/overdue requests

**Current status:** Registered in product catalogue only. No code implementation. Awaiting Phase 2 development.

---

## 11. Key Features

### Multi-Tenancy
- All data strictly isolated by `tenant_id`
- Users, groups, requests, files, and audit logs belong to exactly one tenant
- Platform Admin manages tenants without accessing their data

### Workflow Engine
- Template-based, reusable approval chains
- Sequential or parallel step execution
- Per-step SLA (default 3 business days)
- 3-level escalation ladder → auto-cancel at Level 3
- Delegation support for out-of-office coverage

### File Management
- Upload to MinIO (S3-compatible) with SHA256 integrity check
- Maximum file size: **5 GB**
- Presigned download URLs with **120-second TTL**
- Configurable auto-expiry: 30, 60, 90, or 180 days
- 48-hour pre-expiry warning notifications
- File bytes deleted on expiry; metadata retained forever

### Structured Data Sharing
- Register external DB connections (PostgreSQL, MySQL, Oracle, etc.)
- Select tables/columns visually or write custom SQL
- Live schema introspection with JSONB caching
- Preview results before attaching to request
- Export delivered as CSV

### External Recipient Portal
- Share data with organizations that are not on the platform
- Generate magic-link tokens (72h TTL, max 10 downloads)
- Recipients must accept DPA before any download
- IP address and user agent logged at DPA acceptance (BRD §8.1)
- Rate limited: 30 requests/minute per token prefix
- Tokens can be revoked at any time

### Delegation (BRD §2.3)
- Users set an out-of-office window with a named delegate
- Delegate can approve workflow steps on behalf of primary assignee
- Full audit trail: `delegated_from_user_id` links action to original assignee
- Time-bounded: automatically expires at `delegation_end`

### Audit Trail
- Immutable, append-only `t_audit_events` table
- Every platform action logged with before/after state snapshots (JSONB)
- Actor IP + user agent captured on every event (BRD §8.1)
- CSV export with automatic classification (Confidential if personal data present)
- The export action itself is audited (EC-21 compliance)

### PDPL Compliance
- Personal data flagged and tracked in all requests
- Legal basis recorded per request
- Retention enforced automatically
- DPA acceptance tracked for external downloads
- Platform Admin isolated from all data-controller content (BRD §2.1)
- Saudi business calendar (Fri/Sat weekends + configurable holidays)

### Rate Limiting
- Pickup portal: 30 requests/minute per token prefix (Redis sliding window)
- Prevents brute-force token enumeration

---

## 12. Configuration Reference

All settings are environment-variable driven via `app/core/config.py`.

### Database

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `postgres` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `datasharing_dev` | Database name |
| `POSTGRES_USER` | `dsplatform` | DB user |
| `POSTGRES_PASSWORD` | — | DB password |

### Redis

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis database index |

### MinIO (File Storage)

| Variable | Default | Description |
|---|---|---|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO endpoint |
| `MINIO_ACCESS_KEY` | — | Access key |
| `MINIO_SECRET_KEY` | — | Secret key |
| `MINIO_BUCKET` | — | Default bucket name |
| `MINIO_SECURE` | `false` | Use HTTPS |
| `MAX_FILE_SIZE_BYTES` | `5368709120` | 5 GB max upload |

### Keycloak (Identity)

| Variable | Default | Description |
|---|---|---|
| `KEYCLOAK_SERVER_URL` | `http://keycloak:8080` | Keycloak URL |
| `KEYCLOAK_REALM` | `datasharing-dev` | Realm name |
| `KEYCLOAK_CLIENT_ID` | `datasharing-backend` | Client ID |
| `KEYCLOAK_CLIENT_SECRET` | `dev-client-secret` | Client secret |
| `KEYCLOAK_ADMIN_USER` | `admin` | Admin username |
| `KEYCLOAK_ADMIN_PASSWORD` | `admin` | Admin password |

### Email (SMTP)

| Variable | Description |
|---|---|
| `SMTP_HOST` | SMTP server host |
| `SMTP_PORT` | SMTP port (1025 for MailHog dev) |
| `SMTP_USE_TLS` | Enable TLS |
| `SMTP_USER / SMTP_PASSWORD` | SMTP credentials |
| `EMAIL_FROM` | Sender address |
| `INVITATION_FROM_EMAIL` | Invitation sender address |

### Pickup Portal

| Variable | Default | Description |
|---|---|---|
| `PICKUP_TOKEN_TTL_HOURS` | `72` | Magic-link expiry |
| `PICKUP_TOKEN_MAX_DOWNLOADS` | `10` | Downloads per token |
| `PICKUP_DOWNLOAD_URL_TTL_SECONDS` | `120` | Presigned URL validity |
| `PICKUP_RATE_LIMIT_PER_MINUTE` | `30` | Rate limit per token |

### Background Workers

| Variable | Default | Description |
|---|---|---|
| `WORKER_EXPIRY_CHECK_INTERVAL_MINUTES` | `60` | File expiry check interval |
| `WORKER_SLA_CHECK_INTERVAL_MINUTES` | `30` | SLA escalation check interval |
| `WORKER_NOTIFICATION_INTERVAL_MINUTES` | `5` | Email queue poll interval |

### Application

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `dev` | Environment name |
| `DEBUG` | `true` | Enable API docs at `/api/docs` |
| `FRONTEND_URL` | `http://localhost:8000` | Frontend URL (for CORS & emails) |
| `FRONTEND_BASE_URL` | `http://localhost:8000` | Base URL |

---

## 13. Dev Setup & Credentials

### Starting the Application

```bash
# 1. Start all backend services
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d

# 2. Set up Keycloak realm (first time only)
docker exec ndi-dev3-api-1 python /app/setup/keycloak/setup_realm.py

# 3. Seed test data (first time only)
docker cp /tmp/seed_users.py ndi-dev3-api-1:/tmp/seed_users.py
docker exec ndi-dev3-api-1 python3 /tmp/seed_users.py
```

### Service URLs

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| Keycloak Admin | http://localhost:8080 (admin / admin) |
| MinIO Console | http://localhost:9001 |
| MailHog (email UI) | http://localhost:8025 |

### Test Users

| Email | Role | Password |
|---|---|---|
| `superadmin@datasharing.local` | Platform Admin | `SuperAdmin123!` |
| `orgadmin@acme.local` | Org Admin | `OrgAdmin123!` |
| `nora.dpo@acme.local` | DPO | `Test123!` |
| `ahmed.do@acme.local` | Data Owner (Finance) | `Test123!` |
| `fatima.do@acme.local` | Data Owner (HR) | `Test123!` |
| `youssef.do@acme.local` | Data Owner (IT) | `Test123!` |
| `sara.fin@acme.local` | Requester (Finance) | `Test123!` |
| `omar.fin@acme.local` | Requester (Finance) | `Test123!` |
| `khalid.hr@acme.local` | Requester (HR) | `Test123!` |
| `maha.hr@acme.local` | Requester (HR) | `Test123!` |
| `layla.it@acme.local` | Requester (IT) | `Test123!` |
| `faisal.it@acme.local` | Requester (IT) | `Test123!` |

### Test Tenant

| Field | Value |
|---|---|
| Name | Acme Corporation |
| Slug | `acme` |
| Departments | Finance, Human Resources, IT |

---

## 14. Platform Statistics

| Metric | Value |
|---|---|
| Total API Endpoints | 60+ |
| Database Tables | 25+ |
| Background Workers | 3 |
| Platform Roles | 3 (Platform Admin, Org Admin, User) |
| Data Sharing Product Roles | 5 (Requester, Data Owner, DPO, Source, Receiver) |
| Products in Catalogue | 4 |
| Products Implemented | 1 (Data Sharing) |
| Products Planned | 3 (Data Quality, NDMO, DSR) |
| Max File Size | 5 GB |
| Retention Options | 4 (30 / 60 / 90 / 180 days) |
| SLA Default | 3 business days per step |
| Pickup Token TTL | 72 hours |
| Pickup Max Downloads | 10 per token |
| Supported DB Types | PostgreSQL, MySQL, Oracle + others |
| Calendar | Saudi (Fri/Sat weekend + configurable holidays) |

---

*This document was auto-generated from the NDI platform codebase.*
