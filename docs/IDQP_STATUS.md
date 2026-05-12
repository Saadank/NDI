# IDQP — Build Status & Roadmap

**Last updated:** 2026-05-01
**Phase 1 + Phase 1.5 + Step 4 + UX rework + Step 4.5 + Step 5:** complete and verified end-to-end.
**Next up:** Step 8 (scheduler + concurrency) or Step 6 (Excel + LLM SQL).

---

## Where we are

The Intelligent Data Quality Platform is a sibling product to Data Sharing inside the `DataSharing-1st` monorepo. After Phase 1.5 (the Informatica-inspired restructure), the unit of work is the **Profile Asset** — a named, saveable, owner-bound entity that bundles a source binding (connection + schema + table), profiling configuration (sampling, drill-down, AI on/off), and history (scans, active rules, issues).

**Live demo path:** `http://localhost:8000/dq` → log in → see the Profiles list → click a profile → walk Definition / Rules / Scans / Issues sub-tabs.

**API surface:** all endpoints under `/api/v1/products/data-quality/` are gated by the tenant having `data_quality` enabled in `t_tenant_products`.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────┐
│  Profile Asset  (dq.t_dq_profiles)                      │
│  ├ name + location_path + description                   │
│  ├ source binding: connection_id + schema + table       │
│  ├ profiling config: sampling_mode, sample_size,        │
│  │                   drill_down, ai_enabled             │
│  └ owns ─────────────────────────────────────────────── │
│         │                                               │
│         ├─→ scans (dq.t_dq_scans)                       │
│         │     ├─→ column_profiles (descriptive stats)   │
│         │     └─→ issues (validator findings)           │
│         │                                               │
│         └─→ active_rules (dq.t_dq_active_rules)         │
│              ↑                                          │
│              │ matched against ↓                        │
│              dictionary concepts (dq.t_dq_concepts)     │
└─────────────────────────────────────────────────────────┘
```

### Data flow per scan

```
1. User triggers a scan on a Profile
2. Profiler:
   a. reads profile config (sampling, etc.)
   b. builds qtable = "schema"."table"  OR  (SELECT * FROM ... LIMIT n)
   c. for each column → runs aggregates → persists pattern signatures
                       (no raw values stored)
3. Validator (runs after profile completes):
   a. reads active_rules for this profile (auto_applied + approved only)
   b. for each rule → generates SQL assertion → runs on FULL table
                     (validator never samples — must count ALL violations)
   c. persists per-(scan, rule) issue with status = pass / fail / error
                                       and pattern signatures of violators
```

### Privacy posture

**No raw row values are ever stored in DQ tables.** Pattern detection samples values into app memory, derives a tokenized signature (`Aaa-999`, `EMAIL`, `UUID`, `ISO_DATE`, `IPV4`, `PHONE`, `IBAN`), and persists only the signature distribution. Live values can be inspected via a future "live peek" endpoint that fetches on demand without persistence.

---

## What's deployed (data state at session end)

| Table | Rows | Notes |
|---|---|---|
| `dq.t_dq_profiles` | 8 | 6 backfilled from migration 018 + 2 demos |
| `dq.t_dq_concepts` | 19 | 10 validity + 6 completeness + 3 uniqueness |
| `dq.t_dq_table_types` | 3 | `users` (master_data), `transactions` + `holding_snapshots` (transaction) |
| `dq.t_dq_active_rules` | 20 | matcher decisions, approve/block edits preserved |
| `dq.t_dq_scans` | 0 | cleared at session end (history retained in repo as a SQL one-shot) |
| `dq.t_dq_column_profiles` | 0 | cascade-cleared with scans |
| `dq.t_dq_issues` | 0 | cascade-cleared with scans |
| `dq.t_dq_score_history` | 0 | cascade-cleared with scans (Step 4) |
| `dq.t_dq_score_thresholds` | 6 | one default `'*'` row per existing tenant (Step 4) |

**To re-clear scan history later:**
```bash
docker exec -i datasharing-1st-postgres-1 \
    psql -U dsplatform -d datasharing_dev < docs/dev_clear_dq_scans.sql
```

**Test credentials:** `superadmin@datasharing.local` / `SuperAdmin123!`
**Postgres container:** `datasharing-1st-postgres-1` (DB `datasharing_dev`, user `dsplatform`)
**Test source:** Postgres connection `990cd8d7-3951-4a3c-810e-9a987d61ab19` (Railway, 6 tables)

---

## What we built — chronological

### Phase 1 — Foundation (all complete)

| Step | What landed |
|---|---|
| **1** — Semantic typing | Migration 011: `dq.t_dq_table_types`. UI lets the team tag tables as `master_data` / `transaction` / `event_log` / `reference` / `staging` / `snapshot`. Type drives rule applicability. |
| **2** — Profiler | Migration 012: `dq.t_dq_scans` + `dq.t_dq_column_profiles`. `ProfilerService` runs SQL aggregates per column (counts, distinct, min/max, mean/stddev, length stats, pattern signatures, inferred column type). |
| **2 (privacy)** | Migration 013: dropped `min_value`, `max_value`, `top_values`, `sample_values`. Replaced with `dominant_pattern` + `pattern_conformance_rate` + `top_patterns` (tokenized shapes only). |
| **2.5** — Schema-wide scan | `POST /scans/batch` + per-connection `asyncio.Semaphore` (cap=4) so a batch can't smash the source DB. |
| **3a** — Dictionary | Migration 014: `dq.t_dq_concepts` per-tenant. 19 seed concepts across 3 dimensions. CRUD UI in Dictionary tab. |
| **3b** — Concept matcher | Migration 015: `dq.t_dq_active_rules`. Two-tier matcher: (1) fuzzy via `difflib` on synonym list, (2) Anthropic Haiku 4.5 fallback for ambiguous cases. HIGH-confidence → auto_applied; MEDIUM/LOW → proposed (await human approval). |
| **3c** — Validator | Migration 016: `dq.t_dq_issues`. Five rule evaluators (`not_null`, `max_null_rate`, `no_pseudo_nulls`, `unique`, `format_regex`) with per-rule failure isolation. Validator runs at the end of every scan. |

### Step 5 — Governed exception engine (all complete — 2026-05-01)

| Step | What landed |
|---|---|
| **5.a** | Migration 022: `t_dq_exceptions` + history trigger. Reason categories (`legacy_data` / `business_accepted` / `in_progress` / `data_provider` / `other`), optional `violation_count_ceiling`, mandatory `expires_at`. Partial unique index — at most one active exception per active rule. Replacements revoke the prior row first. |
| **5.b** | `ExceptionRepository` + `ExceptionService` — full CRUD with admin-only mutations, 365-day max horizon, automatic re-score on create / revoke / extend. |
| **5.c** | ScoringService rewritten to compute raw vs governed separately. Per issue: `raw_pass = 1 - violation_rate`; `governed_pass = 1.0` iff an active exception covers the rule (no ceiling, OR violation_count ≤ ceiling). Tier band uses governed score. |
| **5.d** | `/exceptions` router: `GET /profile/{id}` (with `?include_revoked=`), `POST /` (creates or replaces; default 90-day expiry), `POST /{id}/revoke`, `PUT /{id}/extend`. |
| **5.e** | UI: new **Exceptions** sub-tab on profile detail. Suppress button on failing rules in the Metrics tab opens a modal (reason / explanation / ceiling / days). Donuts show governed score; raw line appears only when raw ≠ governed. Suppressed rule rows get a violet badge. |
| **5.f** | Read-time expiry: rows with `status='active' AND expires_at > now()` are the only ones honored by scoring or list-active. Rows past expiry get a "past expiry" pill in the UI. The Step 8 sweeper will eventually flip them to `status='expired'` for cleanliness. |

### Step 4.5 — Dense column dashboard (superseded by Step 5.5 — see below)

| Step | What landed |
|---|---|
| **4.5.a** | Profiler now captures `character_maximum_length` (Postgres/MySQL/MSSQL) / `data_length` (Oracle) per column and stashes it on `raw_metrics.declared_length`. No migration — JSONB. |
| **4.5.b** | Frontend Scans → per-column profile view gains a **Classic ↔ Dense** toggle. Dense mode shows: a horizontal `null / distinct / repeated` distribution bar per column, length cell `max / declared` with an **over-allocated** flag, and per-column rule-status dots. **Replaced 2026-05-09:** the Classic / Dense toggle was removed and the views replaced with **Table / Tiles** (see Step 5.5). The `raw_metrics.declared_length` capture from 4.5.a stays — it just isn't surfaced in the new views. |

### Step 5.5 — Scan-results tile redesign (all complete — 2026-05-09)

Per stakeholder review, the per-column profile view was rebuilt around the
8 metrics shown in the design mock: max value, min value, mean / median /
percentiles, pattern, null, min / max length, stddev, most-frequent values.

| Step | What landed |
|---|---|
| **5.5.a** | Migration 023: adds `min_value`, `max_value`, `p25_value`, `p75_value`, `p95_value` to `t_dq_column_profiles`. **Partially reverses 013** — header documents the privacy trade-off (min/max is a single-row leak; persisting them was the explicit ask). Top values stay live-only. |
| **5.5.b** | `ProfilerService._compute_numeric_extras` now collects min/max + median + p25/p75/p95. Percentiles use `percentile_cont` (Postgres / Oracle / MSSQL) or `quantile()` (ClickHouse); MySQL/MariaDB get null tiles since neither dialect has a clean built-in. |
| **5.5.c** | New endpoint `GET /profiles/{id}/columns/{col}/sample-stats?top_limit=N`. Live-fetches the top-N most-frequent non-null values via the existing connector. **Nothing persisted.** Backs the "Top values" tile / cell. Cached client-side per `(profile_id, column_name)` so toggling Table↔Tiles doesn't re-fetch. |
| **5.5.d** | Frontend: Classic view and Dense view both removed. New **Table** view = trimmed columns matching the picture (#, Column, Null, Length, Min·Max, Mean, Median, StdDev, Pattern, Top values button). New **Tiles** view = one card per column with a 3-col CSS-grid of 8 tiles arranged like the mock (Max / Min / [Mean·Median·percentiles tall tile] · Pattern / Null / [continued] · StdDev / Top values / Length). Top-values tile/cell is on-demand via a `Show` button. |

### First-run UX rework (all complete — 2026-04-29)

After walking through the tool as a new user, the team flagged that the original
flow was confusing (semantic-type tagging in the wrong place, dictionary dumped
all 19 concepts in one screen, profiles non-empty due to the 1.5 backfill, no
fast-iteration scan mode, no manual rule attachment). This pass reorganized
around the actual workflow: **connect → browse → tag-on-create → bind rules → scan**.

| Step | What landed |
|---|---|
| **UX.A** | New `GET /tables/connections/{id}/preview?schema_name=&table_name=&limit=N` returns column metadata + a small live SELECT sample. Nothing persisted. UI: Sources tab now has a **Preview** button per row that opens a modal with columns and 10 sample rows side-by-side. |
| **UX.B** | Dictionary tab now lands on a **dimension picker** (Completeness / Validity / Uniqueness tiles with concept counts). Click a tile → only that dimension's rules. Back link returns to the picker. |
| **UX.C** | Six backfilled demo profiles deleted (`DELETE FROM dq.t_dq_profiles WHERE description LIKE 'Auto-created during Phase 1.5 backfill%'`). Profile **creation modal** now includes the **semantic type** dropdown — set once at create, persisted via the existing `/tables/.../assign` endpoint. The Sources tab no longer carries a Type column. |
| **UX.D** | Two new scan modes (BRD §4.5 fast-iteration): `POST /scans/validate-only` skips the slow per-column profiler and re-runs only the active rules. Optional `dimension` and `active_rule_ids[]` narrow further. Validator + scoring still run. UI buttons on the profile's Scans sub-tab: **Full scan** / **Re-validate only** / **Re-validate dimension…** Validate-only scans show as `type=rules-only` in the table and don't link to the per-column profile view. |
| **UX.E** | New `POST /active-rules/manual` hand-binds a (column, concept) pair on a profile. Lands as `matched_by='manual'`, `confidence='high'`, `approval_status='auto_applied'`. The matcher's apply path already preserves `approved/blocked` rows; manual rules are durable across re-applies. UI: **+ Add rule** button on the Rules sub-tab opens a modal with column + dimension + concept selectors. |

### Step 4 — Scoring (all complete)

| Step | What landed |
|---|---|
| **4.a** | Migrations 020 + 021: `t_dq_score_history` + `t_dq_score_thresholds`. One score row per `(scan, dimension)` plus an `overall` aggregate; tenant-level tier bands default to 0.95 / 0.70. |
| **4.b** | `ScoreRepository` + `ScoringService` — aggregates `1 - violation_rate` per dimension, classifies into `good` / `acceptable` / `not_acceptable` / `no_rules`, persists raw + governed + (optional) severity-weighted scores. |
| **4.c** | Validator pipeline calls `score_scan` immediately after issue inserts (best-effort — failure is logged, scan still succeeds). Recompute endpoint lets users re-score a scan after threshold edits. |
| **4.d** | `/scores` router: `GET /profile/{id}/metrics`, `GET /profile/{id}/trend`, `POST /scan/{id}/recompute`, `GET/PUT /thresholds` (admin-only PUT). Trend deltas use `LAG(pass_rate)` over scan_id. |
| **4.e** | UI: new **Metrics** sub-tab in profile detail modal — donuts per dimension + overall, stacked pass/fail/error bars per dimension, rule-occurrences table. Δ pp arrow vs previous scan. |

### Phase 1.5 — Informatica-inspired restructure (all complete)

After reviewing Informatica Cloud Data Quality / CLAIRE screenshots, we restructured around the **Profile Asset** model:

| Step | What landed |
|---|---|
| **3.5.a** | Migrations 017 + 018: `dq.t_dq_profiles` + history trigger. `profile_id` FK added (nullable) to scans / active_rules / issues + backfill (one profile per distinct `(tenant, conn, schema, table)`). |
| **3.5.b** | `ProfileRepository` + `ProfileService` — CRUD, list-by-location, clone (copies config but starts empty history). |
| **3.5.c** | `/profiles` router: GET list, POST create, GET/PUT/DELETE id, POST `/{id}/clone`. Wired into `main.py`. |
| **3.5.d** | Refactored scans / active-rules / issues paths to take `profile_id` instead of the (conn, schema, table) tuple. Migration 019 tightened `profile_id` to NOT NULL. |
| **3.5.e** | Profiler honors `sampling_mode` (`first_n` / `random`) by wrapping the target table in a LIMIT-bounded subquery. Per-dialect SQL: `LIMIT n` for PG/MySQL/CH, `TOP n` for MSSQL, `FETCH FIRST n ROWS ONLY` for Oracle. Validator deliberately does NOT sample — violation counts must reflect the full table. |
| **3.5.f** | UI restructured: Profiles list as the home, per-profile detail modal with sub-tabs (Definition / Rules / Scans / Issues). Sources tab repurposed for semantic typing only with a "+ Profile" button per row. |

---

## Key architectural decisions (do NOT re-litigate without checking)

1. **Schema isolation in `dq.*`** — every DQ table lives in its own Postgres schema. Cross-schema FKs to `public.t_tenants` / `public.t_users` / `public.t_connections`.
2. **Metadata-only storage (with one explicit exception)** — pattern signatures replace raw `top_values` / `sample_values`. Migration 023 re-introduced `min_value` and `max_value` as a deliberate trade-off (see that migration's header) — they're single-row leaks, but persisting them lets the redesigned scan-results tiles render without a per-column live query. **Top values are still never persisted** — the live-peek endpoint `/profiles/{id}/columns/{col}/sample-stats` covers them.
3. **Three dimensions only (Phase 1)** — completeness, validity, uniqueness. Consistency / timeliness / accuracy come back when their rule libraries are designed.
4. **Dictionary-driven, not column-binding** — instead of binding one rule to N columns one-by-one (Informatica's pattern), the matcher reads each column's name and proposes concepts whose synonyms match. PK `not_null` is *not* a rule — the database already enforces it.
5. **Two-tier matcher (permanent, not temporary)** — fuzzy first (free, deterministic, fast) → LLM Haiku 4.5 only when fuzzy fails (semantic, handles abbreviations / non-English). Per-call dictionary cached via Anthropic prompt caching.
6. **HIGH → auto_applied, MEDIUM/LOW → proposed** — high-confidence matches activate immediately; lower-confidence ones await human approve/block.
7. **Per-scan immutable issues** — `UNIQUE(scan_id, active_rule_id)`. History = the table itself; trends are computed via window functions over time, not separate tables.
8. **Profile Assets are the unit of work** (Phase 1.5) — a named entity that owns scans, rules, and history. Source binding (connection / schema / table) is immutable post-create — clone if you want a variant.
9. **Profiler may sample, validator never does** — descriptive stats can be approximated; violation counts must be honest.
10. **Local Ollama for LLM features** (was Anthropic Haiku 4.5 through Step 5). Default model `qwen2.5-coder:7b` — purpose-built for code/SQL/JSON, ~16s warm calls on RTX 2080. Configurable via `DQ_LLM_PROVIDER` / `DQ_LLM_BASE_URL` / `DQ_LLM_MODEL`. When the provider is unreachable, matcher falls back to fuzzy-only and AI endpoints return `llm_unavailable`.

## What we explicitly REJECTED from Informatica

| Their pattern | Why we skip |
|---|---|
| Storing raw values + watermark redaction | We're metadata-only. Live-peek when needed. |
| One-rule-per-column-binding (16 verbose rows of "Completeness_Rule") | Our concept matcher does this automatically. We borrow their *transparency* (a per-rule listing of bound columns) without the verbosity. |
| Two profile assets per source for dimension scoping | A workaround for their per-asset dimension limit. Our model handles all 3 dimensions in one profile. |
| Severity-blind scoring | We keep severity in the data; weighting will be an opt-in toggle in Step 4. |
| Generic descriptions ("check the completeness" 16 times) | Already prevented by our concept-name validation. |
| No raw vs governed score split | We will keep this for Step 5 — exceptions need a separate score path. |

---

## File-by-file inventory

### Migrations (`backend/setup/db/`)

| # | File | Adds |
|---|---|---|
| 011 | `dq_core.sql` | `dq` schema; `t_dq_table_types` + history (idempotent self-heal moves any pre-existing tables out of `public` into `dq`) |
| 012 | `dq_profiler.sql` | `t_dq_scans` + `t_dq_column_profiles` |
| 013 | `dq_profile_metadata_only.sql` | drops raw-value columns, adds `dominant_pattern` + `pattern_conformance_rate` + `top_patterns` |
| 014 | `dq_concepts.sql` | `t_dq_concepts` + history trigger |
| 015 | `dq_active_rules.sql` | `t_dq_active_rules` + history trigger |
| 016 | `dq_issues.sql` | `t_dq_issues` |
| 017 | `dq_profiles.sql` | `t_dq_profiles` + history trigger (Phase 1.5) |
| 018 | `dq_profile_fks.sql` | nullable `profile_id` FKs on scans/rules/issues + backfill |
| 019 | `dq_profile_id_required.sql` | tightens `profile_id` to NOT NULL |
| 020 | `dq_score_history.sql` | `t_dq_score_history` — per-(scan, dimension) pass-rate, tier, raw/governed/weighted scores (Step 4) |
| 021 | `dq_score_thresholds.sql` | `t_dq_score_thresholds` — per-tenant tier bands + severity-weighting toggle (Step 4) |
| 022 | `dq_exceptions.sql` | `t_dq_exceptions` + history trigger — governed exceptions with reason, ceiling, expiry (Step 5) |
| 023 | `dq_column_profile_extended_stats.sql` | adds `min_value`, `max_value`, `p25_value`, `p75_value`, `p95_value` to `t_dq_column_profiles`. **Partially reverses 013** — min/max are now persisted (header documents the privacy trade-off). Top values remain live-only. Backs the redesigned scan-results Tiles view. |
| 024 | `dq_imports_proposals_llm_calls.sql` | Step 6 data model — `t_dq_imports` (Excel upload state machine), `t_dq_glossary_terms` (BRD Table 11), `t_dq_llm_calls` (audit), `t_dq_proposals` (human-review queue). |

### Backend (`backend/app/products/data_quality/`)

```
data_quality/
├── dependencies.py             require_data_quality (product gate)
├── permissions.py              can_use_dq, DQ_TEAM_ROLE
├── enums/
│   ├── table_semantic_type.py
│   ├── dq_dimension.py
│   └── severity.py
├── repositories/
│   ├── table_type_repository.py
│   ├── scan_repository.py
│   ├── column_profile_repository.py
│   ├── concept_repository.py
│   ├── active_rule_repository.py
│   ├── issue_repository.py
│   ├── profile_repository.py        ← Phase 1.5
│   ├── score_repository.py          ← Step 4
│   └── exception_repository.py      ← Step 5
├── services/
│   ├── table_type_service.py
│   ├── profiler_service.py          ← runs aggregates + sampling
│   ├── concept_seed.py              ← 19 default concepts
│   ├── concept_service.py
│   ├── fuzzy_matcher.py             ← three-tier difflib match
│   ├── llm_matcher.py               ← Anthropic Haiku 4.5 + prompt caching
│   ├── active_rule_service.py       ← matcher orchestrator
│   ├── validator_service.py         ← five rule evaluators
│   ├── profile_service.py           ← Phase 1.5
│   ├── scoring_service.py           ← Step 4 + raw/governed split (Step 5)
│   └── exception_service.py         ← Step 5 (governed exceptions)
└── routers/
    ├── health.py
    ├── connections.py
    ├── tables.py
    ├── concepts.py
    ├── scans.py
    ├── active_rules.py
    ├── issues.py
    ├── profiles.py                  ← Phase 1.5
    ├── scores.py                    ← Step 4 (metrics, trend, recompute, thresholds)
    └── exceptions.py                ← Step 5 (create / revoke / extend)
```

### Frontend (`frontend/`)

- `dq.html` — single-file standalone UI served at `localhost:8000/dq`. ~1470 lines. Uses fetch + plain HTML/JS. Tabs: Profiles (default) · Sources · All scans · Dictionary. Per-profile detail modal with internal tabs (Definition / Rules / Scans / Issues).

### Config

- `backend/app/core/config.py` — added `ANTHROPIC_API_KEY`, `DQ_LLM_MODEL`, `DQ_LLM_MAX_OUTPUT_TOKENS`.
- `backend/pyproject.toml` — added `anthropic>=0.40.0`.
- `.env.dev` — `ANTHROPIC_API_KEY=` (empty → fuzzy-only mode).
- `backend/app/main.py` — registers DQ routers under `/api/v1/products/data-quality/` with `require_data_quality` gate.

### Documentation

- `docs/IDQP_STATUS.md` — this file.
- `docs/dev_clear_dq_scans.sql` — re-runnable scan-history wiper.

---

## Next steps

### Step 4.5 — Dense column dashboard (Informatica's "Results" pic 5)

**Goal:** replace today's per-column profile view with the horizontal value-distribution + all-stats grid.

- Compute `value_distribution` = `(null_count, distinct_count, non_distinct_count)` ratio — already have all three.
- Compute documented-vs-detected type gap: `declared_data_type` length vs detected `max_length`. Flag when `actual << declared` (over-allocated columns).
- Reshape Results UI into the dense grid with color bars + rule-icon indicator per column.

### Step 5 — Governed exception engine (BRD §4.8 / FR-EXC)

- `dq.t_dq_exceptions(issue_signature, reason_category, explanation, owner, expires_at, status)`.
- Exception expiry worker reactivates expired exceptions.
- Scoring engine consults active exceptions to compute **governed score** alongside raw score.

### Step 6 — Excel upload pipeline + LLM SQL generation (biggest single step)

**Detailed plan: [`docs/IDQP_STEP6_PLAN.md`](IDQP_STEP6_PLAN.md)** — file layout, migration 023 schema, 5 LLM prompt purposes, validators, API surface, UI plan, and 9 sub-steps (6.0 → 6.8).

Summary of what changes vs the original outline:
- **Three entry points**, not one: Excel uploads (BRD Tables 11–13) **plus** an interactive `POST /concepts/draft-from-nl` that lets users author a concept by typing natural language in the Dictionary tab.
- **`data_quality/ai/` subpackage** quarantines all LLM-touching code. The deterministic rule engine never imports from `ai/`; only the proposal service crosses the boundary, at approval time.
- **Easy path / hard path** in Table 12: rows that name `table` + `column` skip column-matching and only call `sql_generation`. Rows without a column run `column_match` first, then `sql_generation` per matched column.
- **Multilingual matching** (e.g. business term "Arabic name" → `A_name` / `name_ar` / `الاسم`) handled by `column_match` returning ranked candidates with confidence; reviewer picks.
- **Requires** ANTHROPIC_API_KEY provisioned.

### Step 7 — Dashboard / Insights

- Home overview (cross-profile aggregates).
- Issue Tracker (filter, CSV export).
- Score Trends across profiles.
- Charts via CDN script tag (Chart.js).

### Step 8 — Scan scheduler + concurrency

- `dq.t_dq_scan_schedules(profile_id, cron, last_run, next_run, max_concurrent)`.
- Worker claims due scans, runs profile→validator pipeline, writes progress.
- Real-time progress endpoint for UI.
- Retry policy (NFR-REL-03).

### Step 9 — Phase 1 hardening

- 10M-row scan in 10 min (NFR-PERF-01).
- 20 concurrent scans (NFR-PERF-05).
- AES-256 credentials verified.
- Backup verification (NFR-REL-05).
- End-to-end demo.

### Phase 2 — AI-driven discovery (BRD §5)

Defer until Phase 1 ships. Adds: baseline builder (after 3 scans per table), pattern detector, Isolation Forest / IQR / z-score numeric anomaly detection, ECOD multivariate, DBSCAN string clustering, LLM root-cause + rule-suggestion review queue, feedback-driven threshold tuning, optional PySpark backend.

---

## How to resume next session

1. **Confirm services up:**
   ```bash
   docker ps --format '{{.Names}}' | grep datasharing
   ```
   Expect `datasharing-1st-api-1` and `datasharing-1st-postgres-1`.

2. **Smoke-test login + Profiles list:**
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/platform/auth/login \
       -H "Content-Type: application/json" \
       -d '{"username":"superadmin@datasharing.local","password":"SuperAdmin123!"}' \
       | python -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
   curl -s -H "Authorization: Bearer $TOKEN" \
       http://localhost:8000/api/v1/products/data-quality/profiles
   ```
   Expect 8 profiles.

3. **Open the standalone UI:** `http://localhost:8000/dq` → log in → Profiles tab loads → click a profile → walk the sub-tabs.

4. **Tell Claude:** "Resume Phase 1.5 — start Step 4 (scoring)." Claude will read `docs/IDQP_STATUS.md` and the memory note, then produce migration 020 and the scoring service.

---

## Open items / not blockers

1. **`ANTHROPIC_API_KEY`** is empty in `.env.dev` — matcher runs in fuzzy-only mode. Provision before Step 6.
2. **PII anonymization helper for LLM prompts** (NFR-SEC-04) — needed before Step 6's column-name → concept matching sees real-world sensitive columns.
3. **Snowflake / BigQuery connectors** — defer until a real source needs them.
4. **Score-degradation alerting** (FR-SCORE-06, "Should Have") — wire into existing notification subsystem during Step 8.
5. **Single role vs full RBAC** — currently anyone with `data_quality` product enabled can use everything. Split into `dq_team_member` / `dq_admin` if needed.
6. **Live-peek endpoint for raw values** — for users investigating an issue or drafting a rule. Fetches via existing connector, returns directly, never persists.

---

## Glossary

| Term | Meaning |
|---|---|
| **Profile / Profile Asset** | Named, saveable DQ unit-of-work bound to one (connection, schema, table). Owns scans + rules + history. |
| **Scan** | One execution of profile + validator on a profile. |
| **Concept** | A named DQ rule template in the dictionary (e.g. `email`, `creation_timestamp_required`). Has synonyms, rule_type, parameter, severity, applies_to_types. |
| **Active rule** | Materialization of a (concept × column) decision after the matcher runs, with approval status. |
| **Issue** | Per-(scan, active_rule) finding with status pass / fail / error and violation count. |
| **Pattern signature** | Tokenized shape of a value: `Aaa-999`, `EMAIL`, `UUID`, etc. Replaces raw values in storage. |
| **Fuzzy matcher** | Three-tier (exact / token / SequenceMatcher) column-name → concept matcher. No LLM call. |
| **LLM matcher** | Anthropic Haiku 4.5 fallback when fuzzy returns nothing. Handles abbreviations, non-English names. |
