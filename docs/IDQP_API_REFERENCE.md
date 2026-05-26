# IDQP API Reference

Complete catalog of HTTP API endpoints for the **Intelligent Data Quality Platform (IDQP)**. This document is for frontend developers building UI screens.

**Base URL:** `/api/v1/products/data-quality`

**Auth header:** `Authorization: Bearer <access_token>` — all endpoints require authentication.

**Product gate:** All routes require the tenant to have the `data_quality` product enabled and the user to be one of:
- Platform Admin / Org Admin
- User with `dq_team_member` product role

**Pagination / limits:** Most list endpoints accept `limit` (with documented max). No `page` pagination — lists return `{ items: [...] }`.

---

## Table of Contents

- [Profiles](#profiles)
- [Scans](#scans)
- [Sources / Connections](#sources--connections)
- [Tables (Semantic Types & Preview)](#tables-semantic-types--preview)
- [Dictionary (Concepts)](#dictionary-concepts)
- [Active Rules](#active-rules)
- [Issues](#issues)
- [Scores, Metrics & Thresholds](#scores-metrics--thresholds)
- [Exceptions](#exceptions)
- [AI / LLM-Assisted Workflows](#ai--llm-assisted-workflows)
- [Excel Imports](#excel-imports)
- [Health](#health)
- [Roles Glossary](#roles-glossary)
- [Conventions & Frontend Notes](#conventions--frontend-notes)

---

## Profiles

The **Profile Asset** is the unit of work. Source binding (`connection_id`, `schema_name`, `table_name`) is immutable — clone to retarget.

Base path: `/profiles`

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| GET | `/profiles` | List profiles for tenant | dq_team_member | query: `location_path?`, `connection_id?` | `{ items: [Profile] }` |
| POST | `/profiles` | Create new profile asset | dq_team_member | `name`, `description?`, `location_path`, `connection_id`, `schema_name`, `table_name`, `sampling_mode` (default `all`), `sample_size?`, `drill_down`, `ai_enabled` | `{ detail, profile }` |
| GET | `/profiles/{profile_id}` | Get profile details | dq_team_member | — | Profile object |
| PUT | `/profiles/{profile_id}` | Update profile metadata | dq_team_member | `name?`, `description?`, `location_path?`, `sampling_mode?`, `sample_size?`, `drill_down?`, `ai_enabled?` | `{ detail, profile }` |
| DELETE | `/profiles/{profile_id}` | Delete profile + cascade (scans, rules, issues) | dq_team_member | — | `{ detail }` |
| POST | `/profiles/{profile_id}/clone` | Clone profile with new name | dq_team_member | `new_name` | `{ detail, profile }` |
| GET | `/profiles/{profile_id}/columns/{column_name}/sample-stats` | Live peek at column's top-N values | dq_team_member | query: `top_limit?` (default 10, max 50) | Column stats + frequencies |

---

## Scans

Profiling and validation execution. Profiler may sample; validator never does.

Base path: `/scans`

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| POST | `/scans` | Start a profiling scan on a profile | dq_team_member | `profile_id` | `{ detail, scan }` (pending) |
| POST | `/scans/validate-only` | Re-validate without re-profiling | dq_team_member | `profile_id`, `dimension?` (`completeness` \| `validity` \| `uniqueness`), `active_rule_ids?` | `{ detail, scan }` |
| POST | `/scans/batch` | Queue scans for multiple profiles | dq_team_member | `profile_ids[]` (1–500) | `{ detail, queued, ... }` |
| GET | `/scans` | List scans with filters | dq_team_member | query: `profile_id?`, `connection_id?`, `schema_name?`, `table_name?`, `limit?` (default 100, max 500) | `{ items: [Scan] }` |
| GET | `/scans/{scan_id}` | Get scan details & status | dq_team_member | — | Scan object with metrics |
| GET | `/scans/{scan_id}/profiles` | Per-column profile rows for a scan | dq_team_member | — | `{ items: [ColumnProfile] }` |

---

## Sources / Connections

Read-only view of source-DB connections (credentials redacted).

| Method | Endpoint | Purpose | Auth | Response |
|---|---|---|---|---|
| GET | `/connections/` | List all source-DB connections | dq_team_member | `[{ id, db_type, host, port, database, description, status, created_at }]` |

---

## Tables (Semantic Types & Preview)

Browse tables on a connection, assign semantic types, and preview live data.

Base path: `/tables/connections/{connection_id}`

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| GET | `/tables/connections/{connection_id}` | List tables with semantic-type assignments | dq_team_member | — | `{ items: [Table] }` with type & confidence flags |
| PUT | `/tables/connections/{connection_id}/assign` | Assign semantic type to (schema, table) | dq_team_member | `schema_name`, `table_name`, `semantic_type`, `note?` | `{ detail, row }` |
| GET | `/tables/connections/{connection_id}/preview` | Live peek: columns + N sample rows (no persistence) | dq_team_member | query: `schema_name` (required), `table_name` (required), `limit?` (default 10, max 100) | Column metadata + sample rows |
| DELETE | `/tables/connections/{connection_id}/assign` | Clear semantic type assignment | dq_team_member | `schema_name`, `table_name` | `{ detail }` |

---

## Dictionary (Concepts)

Master library of rule templates. Dictionary-driven — concepts are matched to columns to produce active rules.

Base path: `/concepts`

| Method | Endpoint | Purpose | Auth | Request |
|---|---|---|---|---|
| GET | `/concepts` | List all concepts | dq_team_member | query: `dimension?`, `enabled_only?` |
| POST | `/concepts` | Create new concept / rule template | dq_team_member | `dimension`, `concept`, `synonyms[]`, `rule_type`, `parameter` (dict), `severity` (default `medium`), `applies_to_types[]`, `notes?`, `enabled` (default `true`) |
| GET | `/concepts/{concept_id}` | Get concept details | dq_team_member | — |
| PUT | `/concepts/{concept_id}` | Update concept | dq_team_member | `synonyms?`, `rule_type?`, `parameter?`, `severity?`, `applies_to_types?`, `notes?`, `enabled?` |
| DELETE | `/concepts/{concept_id}` | Delete concept | dq_team_member | — |
| POST | `/concepts/seed-defaults` | Idempotently install default dictionary | dq_team_member | — |

---

## Active Rules

Rules bound to a profile's columns. HIGH-confidence matches auto-apply; MEDIUM/LOW propose for review.

Base path: `/active-rules`

| Method | Endpoint | Purpose | Auth | Request |
|---|---|---|---|---|
| POST | `/active-rules/preview` | Preview matcher results without persisting | dq_team_member | `profile_id` |
| POST | `/active-rules/apply` | Run matcher & persist HIGH matches | dq_team_member | `profile_id` |
| GET | `/active-rules` | List active rules for a profile | dq_team_member | query: `profile_id` (required) |
| POST | `/active-rules/manual` | Manually bind concept to a column (durable across re-applies) | dq_team_member | `profile_id`, `column_name`, `concept_id` |
| POST | `/active-rules/{rule_id}/approve` | Approve a proposed rule | dq_team_member | — |
| POST | `/active-rules/{rule_id}/block` | Block a rule (with reason) | dq_team_member | `reason?` |
| POST | `/active-rules/{rule_id}/unblock` | Unblock a previously blocked rule | dq_team_member | — |

---

## Issues

Scan findings — violations detected by validators.

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| GET | `/issues/scan/{scan_id}` | Issues from a single scan | dq_team_member | — | `{ scan_id, summary, items: [] }` |
| GET | `/issues/profile/{profile_id}` | Issues for profile (latest scan or history) | dq_team_member | query: `latest_scan_only?` (default `true`), `limit?` (default 500, max 2000) | `{ items: [] }` |

> Note: storage is metadata-only — pattern signatures (e.g., `EMAIL`, `Aaa-999`) only, never raw row values.

---

## Scores, Metrics & Thresholds

Per-dimension scoring, trend history, and tier thresholds.

Base path: `/scores`

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| GET | `/scores/profile/{profile_id}/metrics` | Latest dimension scores + delta + rule occurrences | dq_team_member | — | Metrics payload for dashboard donuts |
| GET | `/scores/profile/{profile_id}/trend` | Per-scan score history (newest first) | dq_team_member | query: `limit?` (default 50, max 500) | `{ items: [ScoreHistory] }` |
| POST | `/scores/scan/{scan_id}/recompute` | Recompute scores from current issues (idempotent) | dq_team_member | — | `{ detail, items: [] }` |
| GET | `/scores/thresholds` | Get tenant's score tier thresholds | dq_team_member | — | `{ items: [Threshold] }` (one per dimension + `*`) |
| PUT | `/scores/thresholds` | Upsert tier thresholds | **Admin only** | `dimension` (default `*`), `good_min` (0–1), `acceptable_min` (0–1), `severity_weighting_enabled?` | `{ detail, row }` |

Dimensions: `completeness`, `validity`, `uniqueness`, `overall` (or `*` for global thresholds).

---

## Exceptions

Governed violations — formally accepted exceptions to specific active rules.

Base path: `/exceptions`

| Method | Endpoint | Purpose | Auth | Request |
|---|---|---|---|---|
| GET | `/exceptions/profile/{profile_id}` | List exceptions for profile | dq_team_member | query: `include_revoked?` (default `false`) |
| GET | `/exceptions/{exception_id}` | Exception details | dq_team_member | — |
| POST | `/exceptions` | Create or replace exception for a rule | dq_team_member | `profile_id`, `active_rule_id`, `reason_category`, `explanation` (1–4000 chars), `violation_count_ceiling?`, `expires_at?` (ISO ts) OR `expires_in_days?` (1–365, default 90) |
| POST | `/exceptions/{exception_id}/revoke` | Revoke active exception | dq_team_member | `reason?` |
| PUT | `/exceptions/{exception_id}/extend` | Extend expiry | dq_team_member | `days?` (1–365) OR `until?` (ISO ts) |

---

## AI / LLM-Assisted Workflows

Powered by Anthropic Haiku 4.5 (`claude-haiku-4-5-20251001`). Requires `ANTHROPIC_API_KEY` to be provisioned.

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| POST | `/concepts/draft-from-nl` | Draft a concept from a natural-language description | dq_team_member | `nl_text` (1–2000 chars), `dimension_hint?` | `{ status, draft?, error?, latency_ms, input_tokens?, output_tokens? }` |

---

## Excel Imports

Upload glossary / column_rules / business_rules sheets (Table-11 / Table-13 templates).

Base path: `/imports`

| Method | Endpoint | Purpose | Auth | Request | Response |
|---|---|---|---|---|---|
| POST | `/imports` | Upload an Excel file | dq_team_member | `multipart/form-data`: `kind` (`glossary` \| `column_rules` \| `business_rules`), `file`, `version_label?` | Import metadata + status |
| GET | `/imports` | List imports (newest first) | dq_team_member | query: `kind?`, `status?` | `{ items: [] }` |
| GET | `/imports/template/glossary` | Download Table-11 glossary template | dq_team_member | — | `.xlsx` file |
| GET | `/imports/template/column_rules` | Download Table-13 column-rules template | dq_team_member | — | `.xlsx` file |
| GET | `/imports/{import_id}` | Get import status & errors | dq_team_member | — | `{ id, status, row_count, error_count, errors: [], terms_count }` |

---

## Health

| Method | Endpoint | Purpose | Auth | Response |
|---|---|---|---|---|
| GET | `/health/` | DQ product health check | dq_team_member | `{ status, product, tenant_id, user_id }` |

---

## Roles Glossary

| Role | Meaning |
|---|---|
| **dq_team_member** | Product role granting access to all DQ endpoints |
| **Org Admin** | `ORG_ADMIN` — full access incl. threshold mutations |
| **Platform Admin** | `PLATFORM_ADMIN` — full access incl. threshold mutations |
| **Admin only** | Restricted to Org/Platform Admin (currently only `PUT /scores/thresholds`) |

---

## Conventions & Frontend Notes

### Architectural commitments (fixed — do not work around in UI)
- **Schema isolation** in `dq.*` — all DQ data lives in its own Postgres schema.
- **Metadata-only storage** — never expect raw row values in any response. Pattern signatures only.
- **3 dimensions** in Phase 1: `completeness`, `validity`, `uniqueness` (+ `overall`).
- **Profile Asset** is the unit of work — almost every endpoint accepts `profile_id` somewhere.
- **Source binding is immutable** — to retarget a profile, use `POST /profiles/{id}/clone`.
- **Profiler may sample** (`sampling_mode` = `all` / `first_n` / `random`); **validator never samples** — violation counts are full-table.
- **HIGH-confidence matches → `auto_applied`**, MEDIUM/LOW → `proposed` (need approval).

### Two-tier matcher
1. **Fuzzy-first** (`difflib`) — always runs.
2. **Haiku 4.5 fallback** — only if `ANTHROPIC_API_KEY` is set; otherwise fuzzy-only.

### Response shapes
- **Mutations** typically return `{ detail: "...", <entity>: { ... } }`.
- **Lists** return `{ items: [...] }` (no `page` / `total` — use `limit` to bound).
- **Errors** follow FastAPI conventions: `{ detail: "message" }` with appropriate HTTP status.

### Scans
- New scans are created in **pending** status. The UI should poll `GET /scans/{scan_id}` or refresh metrics after start.
- Use **`/scans/validate-only`** to re-run only validators (cheaper, no profiler) — supports filtering by `dimension` or specific `active_rule_ids`.

### Metrics tab (per profile)
The standalone UI at `localhost:8000/dq` has a per-profile **Metrics** sub-tab with:
- Per-dimension donuts
- Overall donut
- Stacked pass/fail/error bars per scan
- Rule-occurrences table with Δ-pp arrows from prior scan

All data is sourced from `GET /scores/profile/{profile_id}/metrics` + `GET /scores/profile/{profile_id}/trend`.

### First-run UX (current)
- **Sources** tab → **Preview** button → live columns + 10 sample rows modal (`GET /tables/.../preview`).
- **Dictionary** tab → dimension picker (3 tiles), drill in.
- **Profile creator** dialog includes the semantic-type dropdown (no separate "Type" column on Sources).
- **+ Add rule** on a profile's Rules sub-tab → `POST /active-rules/manual` (durable across matcher re-applies).
