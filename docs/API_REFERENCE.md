# API Reference

Complete catalog of HTTP API endpoints for the Data Sharing platform. This document is for frontend developers building UI screens.

**Base URL:** `/api/v1`

**Auth header:** `Authorization: Bearer <access_token>` for all routes except those marked *Public*.

**Pagination:** Endpoints returning lists accept `page` (default `1`) and `limit` (default `20`) as query params.

---

## Table of Contents

- [Platform APIs](#platform-apis)
  - [Auth](#auth)
  - [Users](#users)
  - [Tenants](#tenants)
  - [Groups](#groups)
  - [Invitations](#invitations)
  - [Products](#products)
  - [Holidays](#holidays)
  - [Audit](#audit)
  - [Metrics](#metrics)
- [Data Sharing Product APIs](#data-sharing-product-apis)
  - [Requests](#requests)
  - [Approval Steps](#approval-steps)
  - [Workflow Templates](#workflow-templates)
  - [Files](#files)
  - [Notifications](#notifications)
  - [DB Connections](#db-connections)
  - [Schemas & Structured Data](#schemas--structured-data)
  - [External Recipients](#external-recipients)
- [Public Pickup Portal](#public-pickup-portal)
- [System](#system)
- [Roles Glossary](#roles-glossary)

---

## Platform APIs

### Auth

Base path: `/api/v1/platform/auth`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| POST | `/login` | Authenticate with username & password | Public | `username`, `password` | `access_token`, `refresh_token`, user info |
| POST | `/refresh` | Exchange refresh token for a new access token | Public | `refresh_token` | New `access_token`, `refresh_token` |
| POST | `/logout` | Invalidate refresh token | Public | `refresh_token` | `{ success: boolean }` |

---

### Users

Base path: `/api/v1/platform/users`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List users in tenant | Authenticated | — (query: `page`, `limit`) | Paginated users |
| GET | `/me` | Current user profile (email, roles, tenant) | Authenticated | — | User object |
| POST | `/me/delegation` | Set out-of-office delegation | Authenticated | `delegate_to_user_id`, `delegation_start`, `delegation_end`, `reason` | Updated delegation |
| DELETE | `/me/delegation` | Clear delegation | Authenticated | — | `{ delegation_to_user_id: null }` |
| GET | `/{user_id}` | Get user details | Authenticated | — | User object |
| PUT | `/{user_id}/group` | Assign user to a group | Platform/Org Admin | `group_id` (int or null) | Updated user |

---

### Tenants

Base path: `/api/v1/platform/tenants`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List tenants accessible to user | Authenticated | — | List of tenants |
| GET | `/{tenant_id}` | Get tenant details (name, quotas, retention) | Authenticated | — | Tenant object |
| POST | `/` | Create new tenant | Authenticated | `name`, `slug`, `tenant_type` (default `internal_org`), `name_ar`, `dpo_name`, `dpo_email` | New tenant |
| PUT | `/{tenant_id}/retention-policy` | Set default file retention | Org/Platform Admin | `retention_days` (30, 60, 90, or 180) | Updated tenant |
| PUT | `/{tenant_id}/quotas` | Set storage & seat limits | Platform Admin | `storage_limit_gb`, `seat_limit` | Updated tenant |

---

### Groups

Base path: `/api/v1/platform/groups`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List groups in tenant | Authenticated | — | List of groups |
| POST | `/` | Create group | Authenticated | `name`, `name_ar`, `description` | New group |
| PUT | `/{group_id}` | Update group | Authenticated | `name`, `name_ar`, `description`, `is_active` | Updated group |
| DELETE | `/{group_id}` | Deactivate group | Authenticated | — | Deactivated group |
| PUT | `/{group_id}/data-owner` | Set data owner | Authenticated | `user_id` | Updated group |
| GET | `/{group_id}/members` | List members | Authenticated | — | List of members |
| POST | `/{group_id}/members` | Add member | Authenticated | `user_id` | Updated membership |
| DELETE | `/{group_id}/members/{user_id}` | Remove member | Authenticated | — | Confirmation |

---

### Invitations

Base path: `/api/v1/platform/invitations`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List pending invitations | Authenticated | — | List of invitations |
| POST | `/` | Invite user | Authenticated | `email`, `role`, `product_slug?`, `product_role?`, `tenant_id?` (platform admin only) | Invitation with token |
| POST | `/accept` | Accept invite & create account | Public | `token`, `first_name`, `last_name`, `password` (≥8 chars) | New user + tokens |

---

### Products

Base path: `/api/v1/platform/products`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | Product catalog | Public | — | All products |
| GET | `/me` | Products enabled for current tenant | Authenticated | — | Products + user's product role |
| GET | `/tenants/{tenant_id}` | Products enabled for a tenant | Authenticated | — | Enabled products |
| POST | `/tenants/{tenant_id}` | Enable product for tenant | Authenticated | `product_slug` | Enabled product |
| DELETE | `/tenants/{tenant_id}/{slug}` | Disable product | Authenticated | — | `{ detail: "Product disabled" }` |
| POST | `/users/{user_id}/product-roles` | Assign product role | Authenticated | `product_slug`, `role` | Product role |

---

### Holidays

Base path: `/api/v1/platform/holidays`

Used for SLA business-day calendar.

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List holidays (query: `year?`) | Authenticated | — | List of holidays |
| POST | `/` | Add or update holiday | Org/Platform Admin | `holiday_date`, `name`, `name_ar` | Holiday record |
| DELETE | `/{holiday_id}` | Delete holiday | Org/Platform Admin | — | `{ deleted: holiday_id }` |

---

### Audit

Base path: `/api/v1/platform/audit`

| Method | Endpoint | Purpose | Auth | Query Params | Response |
|---|---|---|---|---|---|
| GET | `/` | List audit events | DPO/Org Admin | `page`, `limit`, `request_id?`, `actor_id?`, `action_type?` | Paginated events |
| GET | `/export` | Export audit trail as CSV | DPO/Org Admin | `request_id?`, `actor_id?`, `action_type?`, `from_date?`, `to_date?` | CSV file (with `X-Audit-Export-*` headers) |

---

### Metrics

Base path: `/api/v1/platform/metrics`

| Method | Endpoint | Purpose | Auth | Response |
|---|---|---|---|---|
| GET | `/tenants/{tenant_id}` | Tenant health: products, user counts, storage usage, request counts, retention | Platform Admin | Metrics object |

---

## Data Sharing Product APIs

All endpoints below require the Data Sharing product to be enabled for the user's tenant.

### Requests

Base path: `/api/v1/products/data-sharing/requests`

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| GET | `/` | List share requests | Data Sharing | — (query: `page`, `limit`, `status?`) | Paginated requests |
| POST | `/` | Create draft request | Data Sharing | See [Request Body — Create Share Request](#request-body--create-share-request) | New request |
| GET | `/{request_id}` | Get request with workflow steps | Data Sharing | — | Full request |
| POST | `/{request_id}/submit` | Submit for approval | Owner | — | Updated request |
| POST | `/{request_id}/cancel` | Cancel request | Owner | — | Cancelled request |

#### Request Body — Create Share Request

```jsonc
{
  "title": "string",
  "purpose": "string",
  "legal_basis": "string",
  "sharing_type": "internal | external",        // default "internal"
  "data_classification": "string",
  "personal_data_involved": true,
  "estimated_data_subjects": 0,
  "data_subject_categories": ["string"],
  "source_description": "string",
  "receiving_tenant_id": 0,
  "receiver_group_id": 0,
  "dpia_confirmed": true,
  "data_type": "file | structured",
  "connection_id": 0,                           // structured only
  "selection_mode": "tables | query",           // structured only
  "selected_items": ["string"],                 // structured only
  "custom_sql": "string",                       // structured only
  "external_recipient": { /* recipient ref */ },
  "delivery_channel": "portal | email | api"
}
```

---

### Approval Steps

Base path: `/api/v1/products/data-sharing/requests/{request_id}/steps/{step_id}`

| Method | Endpoint | Purpose | Auth | Request Body |
|---|---|---|---|---|
| POST | `/approve` | Approve workflow step | Step assignee | `comment?` |
| POST | `/reject` | Reject workflow step | Step assignee | `comment` (required) |
| POST | `/request-changes` | Request changes | Step assignee | `comment` (required) |

---

### Workflow Templates

Base path: `/api/v1/products/data-sharing/workflows`

| Method | Endpoint | Purpose | Auth | Request Body |
|---|---|---|---|---|
| GET | `/templates` | List templates | Data Sharing | — |
| POST | `/templates` | Create template | Workflow Manager | `name`, `sharing_type?`, `data_classification?`, `steps[]` |
| GET | `/templates/{template_id}` | Get template + steps | Workflow Manager | — |
| PUT | `/templates/{template_id}` | Update template | Workflow Manager | `name`, `sharing_type?`, `data_classification?`, `is_active`, `steps[]` |
| DELETE | `/templates/{template_id}` | Deactivate template | Workflow Manager | — |
| GET | `/requests/{request_id}/steps` | Get steps for a request (includes `can_act` flag for current user) | Relevant user | — |

---

### Files

Base path: `/api/v1/products/data-sharing/files`

Multipart upload flow: `initiate` → `PUT /{file_id}/upload` with body.

| Method | Endpoint | Purpose | Auth | Request Body | Response |
|---|---|---|---|---|---|
| POST | `/initiate` | Start upload session | Data Sharing | `request_id`, `filename`, `size`, `mime_type`, `sha256_hash` | `file_id`, `upload_id` |
| GET | `/by-request/{request_id}` | List files attached to request | Data Sharing | — | File list |
| PUT | `/{file_id}/upload` | Upload file body | Data Sharing | `multipart/form-data` (query: `sha256_hash?`) | Completed file |
| GET | `/{file_id}/download-url` | Presigned download URL | Authorized recipient | — | `{ download_url }` |
| DELETE | `/{file_id}` | Delete file | Owner | — (query: `reason?` default `manual`) | `{ detail: "File deleted" }` |

---

### Notifications

Base path: `/api/v1/products/data-sharing/notifications`

| Method | Endpoint | Purpose | Query Params |
|---|---|---|---|
| GET | `/` | List notifications | `unread_only?` |
| POST | `/{notification_id}/read` | Mark notification as read | — |

---

### DB Connections

Base path: `/api/v1/products/data-sharing/connections`

| Method | Endpoint | Purpose | Auth | Request Body |
|---|---|---|---|---|
| GET | `/` | List connections (with credentials) | Data Owner | — |
| GET | `/browse` | List connections (no credentials, for requesters) | Data Sharing | — |
| POST | `/` | Create connection | Data Owner | `db_type`, `host`, `port`, `database?`, `username`, `password`, `description?` |
| POST | `/{connection_id}/test` | Test connection | Data Owner | — |
| DELETE | `/{connection_id}` | Delete connection | Data Owner | — |

---

### Schemas & Structured Data

Base path: `/api/v1/products/data-sharing`

| Method | Endpoint | Purpose | Request Body |
|---|---|---|---|
| GET | `/schemas/{connection_id}` | Cached DB schema (tables, columns, types) | — |
| GET | `/schemas/{connection_id}/browse` | Live schema introspection (may cache) | — |
| POST | `/structured/preview` | Preview query/table result (sample rows) | `connection_id`, `selection_mode` (`tables` \| `query`), `selected_items?`, `custom_sql?`, `limit` (default 100) |
| POST | `/structured/attach` | Attach table/query as dataset to request | `request_id`, `connection_id`, `selection_mode`, `selected_items?`, `custom_sql?`, `filename?` |

---

### External Recipients

Base path: `/api/v1/products/data-sharing/external-recipients`

| Method | Endpoint | Purpose | Auth | Request/Query |
|---|---|---|---|---|
| GET | `/` | List external recipients | Recipient Manager | query: `search?`, `page`, `limit` |
| GET | `/{recipient_id}` | Recipient + contacts + pickup tokens | Recipient Manager | — |
| PATCH | `/{recipient_id}` | Update recipient | Recipient Manager | `org_name?`, `notes?`, `dpa_required?`, `is_active?` |
| POST | `/{recipient_id}/contacts` | Add contact | Recipient Manager | `email`, `name?`, `phone?` |
| PATCH | `/recipient-contacts/{contact_id}` | Update contact | Recipient Manager | `name?`, `phone?`, `is_active?` |
| POST | `/pickup-tokens/{token_id}/revoke` | Revoke pickup token | Recipient Manager | `reason?` |

---

## Public Pickup Portal

Base path: `/api/v1/pickup/{token}`

Unauthenticated (rate-limited). Used by external recipients to download shared data.

| Method | Endpoint | Purpose | Response |
|---|---|---|---|
| GET | `/` | Get pickup overview & DPA status | Request summary, artifacts (if DPA accepted), expiry, download count |
| POST | `/accept-dpa` | Accept Data Processing Agreement | Updated summary with artifacts |
| GET | `/files/{file_id}/download` | Download file (302 redirect to presigned URL) | `302` → S3/MinIO URL |

---

## System

| Method | Endpoint | Purpose | Auth | Response |
|---|---|---|---|---|
| GET | `/health` | API health status | Public | `{ status: "ok", env }` |

---

## Roles Glossary

| Role | Meaning |
|---|---|
| **Public** | No authentication required |
| **Authenticated** | Valid JWT access token required |
| **Platform Admin** | `PLATFORM_ADMIN` — manages all tenants |
| **Org Admin** | `ORG_ADMIN` — manages their own tenant |
| **DPO** | Data Protection Officer — audit access |
| **Data Sharing** | User's tenant must have Data Sharing product enabled |
| **Data Owner** | User designated as data owner of a group or connection |
| **Workflow Manager** | May create/edit workflow templates |
| **Recipient Manager** | May manage external recipients & pickup tokens |
| **Owner** | Creator of the specific request/file |
| **Step assignee** | Current assignee of a workflow step (may include delegated users) |

---

## Notes for Frontend

- **Pagination** is consistent: `page` starts at `1`, `limit` defaults to `20`. Responses include total/count metadata.
- **Query params vs body:** filters like `status`, `search`, `year`, `unread_only` are always query params. Only create/update payloads use JSON bodies.
- **File uploads** go through a two-step flow: `POST /files/initiate` returns a `file_id`, then `PUT /files/{file_id}/upload` sends the bytes as `multipart/form-data`.
- **Audit CSV export** returns a binary response with custom headers (`X-Audit-Export-Id`, `X-Audit-Export-Classification`, `X-Audit-Export-Row-Count`, `X-Audit-Export-Contains-PII`) — read those to display export metadata.
- **Pickup portal** URLs are meant to be shared with external parties; the UI should not require login for those routes.
- **Delegation**: when checking `can_act` on a workflow step, the current user may be acting on behalf of the original assignee if delegation is active — surface this in the UI.
