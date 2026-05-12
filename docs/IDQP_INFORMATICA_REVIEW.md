# IDQP — Informatica Review Prep

**Audience:** Informatica reviewer (CDQ / CLAIRE familiar).
**Status as of:** 2026-05-12 — Phase 1 + 1.5, Steps 4 / 4.5 / 5 / 5.5 / 6.0–6.3 complete.

This doc is structured for a **30–45 min** session:
demo (15) → parity matrix (10) → differentiators (5–10) → open gaps + roadmap (5).

---

## 1. Demo script (15 min)

Walk through `http://localhost:8000/dq` after `superadmin` login. Each section ≈ 2–3 min.

### 1.1 Profiles list (home) — 1 min
- Lead with **"Profile Asset is the unit of work"** — every scan, rule, issue, exception, score belongs to a profile.
- 4 profiles in the dev tenant. Each shows status pill (`good` / `acceptable` / `not_acceptable` / `no_rules`).
- Click **+ New profile** to show the create modal — connection / schema / table + semantic type all in one screen.
- Equivalent in Informatica: their "Asset" → but they need **two** profile assets for the same table when you want completeness + validity scoring in separate views. We do all three dimensions in one.

### 1.2 Open a profile → Definition tab — 1 min
- Read-only summary card: name, location, owner, source binding (connection/schema/table), sampling mode, AI on/off.
- **Immutable source binding** — to retarget, you Clone. Prevents accidental rule drift when a table changes.
- Informatica: editable everywhere. Easier to break.

### 1.3 Rules sub-tab — 3 min
- Active rules table — each row is **(column × concept × confidence)**.
- Three columns to highlight:
  - **Matched by** — `fuzzy` (free, deterministic) or `llm` (Anthropic-style fallback, now via local Ollama)
  - **Confidence** — HIGH / MEDIUM / LOW
  - **Approval status** — `auto_applied` (HIGH), `proposed` (MEDIUM/LOW), `approved` / `blocked` (human override)
- **+ Add rule** — manual binding when the matcher misses. Persistent across re-applies.
- **Contrast with Informatica:** their "Completeness_Rule for column_X" pattern = N rows of nearly-identical "check the completeness" descriptions. Our **dictionary concept** (`email_required`, `national_id_unique`) binds to every column that name-matches via synonyms. ~10× less verbosity, same auditability.

### 1.4 Scans sub-tab → run a fresh full scan — 2 min
- **Run scan now** → background task → status pill goes `pending → running → success` (~10s on the dev tenant).
- Three scan modes:
  - **Full scan** — profiler + validator
  - **Re-validate only** — skip profiler; seconds vs minutes for iteration
  - **Re-validate dimension…** — narrow to completeness OR validity OR uniqueness
- Click the **Profile** button on a completed scan → opens the column-results card.

### 1.5 Scan results — Table view → Tiles view — 3 min ⭐
- This is what landed in **Step 5.5** (just shipped 2026-05-09).
- Table view: per-column row showing the 8 stats from the design mock (max, min, mean·median·percentiles, pattern, null, length, stddev, top values).
- Toggle to **Tiles view** — one card per column with the 8-tile grid laid out exactly like the Informatica "Results" picture 5 the team referenced.
- Click **Show** on the Top values tile/cell → live-fetches from source, never persisted (**privacy hardening** — see §3).
- **What we kept from Informatica:** the dense, statistic-rich layout.
- **What we dropped:** they store top values + min/max in their metadata DB — for any tenant with PII columns (salaries, IDs) that's a real leak. We persist min/max (deliberate trade-off, documented in migration 023) and **fetch top values live**.

### 1.6 Metrics sub-tab — 2 min
- Per-dimension donuts + overall, stacked pass/fail/error bars, rule-occurrences table with **Δ pp arrows** vs the previous scan.
- **Raw vs governed score split** (Step 5) — if any rules are suppressed via an exception, both numbers show side-by-side. Informatica only shows the equivalent of our raw score; governance is a manual side-channel for them.

### 1.7 Exceptions sub-tab — 2 min
- Suppress a failing rule with a reason category (`legacy_data` / `business_accepted` / `in_progress` / `data_provider` / `other`), optional violation-count ceiling, and mandatory expiry (max 365 days).
- Donuts immediately re-render with the governed score.
- Past-expiry exceptions get a yellow pill — they're auto-honored until the Step 8 sweeper flips them.

### 1.8 Dictionary → Draft with AI — 2 min ⭐
- New today (Step 6.3). Top of Dictionary tab, next to **+ Add concept**.
- Type **"Email column must always be present and look like an email"** → click **Draft** → 30–60s wait → LLM returns a structured concept (name / dimension / rule_type / parameter / synonyms / applies_to / confidence).
- **Use this draft** prefills the existing create-concept modal — user edits and saves.
- **Why this matters vs Informatica:** Informatica concept authoring is mouse-driven through a multi-step form. NL drafting reduces what a steward types to write a new concept by ~70%.
- All LLM calls audit-trailed in `dq.t_dq_llm_calls` (model, prompt version, tokens, latency, status, content hashes — never raw text).

---

## 2. Feature parity matrix (10 min)

✅ = shipped today · 🚧 = in flight · 📋 = planned · ❌ = explicitly out of scope

| Capability | Informatica CDQ | IDQP today | Note |
|---|---|---|---|
| Source connections (DB) | ✅ | ✅ | 6 dialects: PG / MySQL / MariaDB / MSSQL / Oracle / ClickHouse |
| Semantic typing (master/transaction/event/reference/staging/snapshot) | ✅ | ✅ | Step 1 |
| Table preview (sample rows) | ✅ | ✅ | Live, not persisted |
| Per-column profiling (counts, distinct, null %, mean, stddev, length) | ✅ | ✅ | Step 2 |
| Pattern signatures (EMAIL / AAA-999) | ✅ | ✅ | Step 2 — tokenized; we **don't** keep raw top values |
| Min / max / median / percentiles | ✅ | ✅ | Step 5.5 — migration 023 |
| Top frequent values | ✅ persisted | ✅ live | Privacy trade-off |
| Dictionary of DQ concepts | ✅ | ✅ | Step 3a — 19 seeds |
| Concept synonyms (multilingual) | ❌ | ✅ | Arabic + transliteration in matcher |
| Column-concept matching | ❌ (manual) | ✅ | Two-tier: fuzzy → LLM |
| Rule approval queue (HIGH auto / MED-LOW proposed) | ❌ | ✅ | Step 3b |
| Manual rule binding | ✅ | ✅ | Step 3.5 UX rework |
| Scan history per profile | ✅ | ✅ | Step 2.5 |
| Per-dimension scoring | ✅ (3 dim limit per asset) | ✅ all 3 dim per profile | Step 4 |
| Severity-weighted scoring | ❌ | ✅ opt-in | Step 4 — per-tenant toggle |
| Score thresholds (tier bands) | ❌ tenant-tunable | ✅ | Step 4 — per-tenant |
| Score history + trends (Δ pp) | partial | ✅ | Step 4 — over scan_id |
| Governed exception engine | side-channel | ✅ | Step 5 — reason / ceiling / expiry |
| Raw vs governed score split | ❌ | ✅ | Step 5 |
| Dense per-column tile dashboard | ✅ | ✅ | Step 5.5 — mirrors their "Results" mock |
| NL → concept draft (Approach 2) | ❌ | ✅ | Step 6.3 — local Ollama (llama3:8b / qwen2.5-coder) |
| Excel uploads (glossary / business rules / column rules) | ✅ | 🚧 | Step 6.4–6.6 — next |
| LLM column matcher (term → column) | ❌ | 🚧 | Step 6.6 — multilingual |
| LLM SQL/regex generation | ❌ | 🚧 | Step 6.5/6.6 |
| Proposal review queue UI | ❌ | 🚧 | Step 6.7 |
| Rollback of imported rules | partial | 🚧 | Step 6.8 |
| Scan scheduler / concurrency | ✅ | 📋 | Step 8 |
| Cross-profile dashboard | ✅ | 📋 | Step 7 |
| Issue tracker + CSV export | ✅ | 📋 | Step 7 |
| Phase 2: anomaly detection / baseline / LLM RCA | ✅ (CLAIRE) | 📋 | Phase 2 |
| Phase 2: PySpark backend for 10M+ tables | ✅ | 📋 | Phase 2 |
| Storing raw row values in metadata DB | ✅ | ❌ | Deliberate — privacy hardening |
| One-rule-per-column-binding verbosity | ✅ | ❌ | Replaced by dictionary concepts |
| Two profile assets per source for dim scoping | ✅ workaround | ❌ | Not needed in our model |

---

## 3. Key differentiators (5–10 min)

Five things to lean on hard if asked "why not just use Informatica?"

### 3.1 Dictionary-driven rules (not one-rule-per-column-binding)
A new column named `customer_email` automatically inherits the `email_required` (completeness) + `is_email` (validity) concepts via synonyms. Adding 50 master-data tables = zero new rule rows; in Informatica that's 50× rule duplication. **Concrete number**: the dev tenant has 19 concepts and 20 active rules across 4 profiles. Informatica's equivalent would be ~80–100 rule rows.

### 3.2 Metadata-only storage (no raw row values)
- The profiler tokenizes values into pattern signatures (`A`/`a`/`9`/punctuation) — **never persists raw values**.
- Migration 013 explicitly drops `top_values` / `sample_values`. The recent migration 023 re-introduced `min_value` / `max_value` as a documented trade-off (tile dashboard needs them) — the header in `023_dq_column_profile_extended_stats.sql` calls out the privacy implication for future readers.
- Top values are fetched **live** via `/profiles/{id}/columns/{col}/sample-stats`, never stored.
- Informatica stores everything. For a tenant with `salary` / `national_id` / `medical_diagnosis` columns, the DQ metadata DB itself becomes a PII surface.

### 3.3 Profile Asset as the unit of work (Phase 1.5)
- Immutable source binding (connection / schema / table) — clone to retarget.
- Owns scans, rules, issues, scores, exceptions via FK ON DELETE CASCADE.
- One name to refer to in audit logs, alerts, dashboards.
- Informatica's per-asset model fights this when you want a single rule applied across 50 tables.

### 3.4 Two-tier matcher (fuzzy → LLM only when needed)
- Fuzzy (`difflib`) handles ~80–90% of straightforward matches for free.
- LLM (now local Ollama on `llama3:latest`, swappable via `DQ_LLM_PROVIDER`) only kicked off for columns fuzzy couldn't classify — typically multilingual / heavily-abbreviated names like `الاسم` or `cstmr_email_addr`.
- **Permanent, not temporary** — even after Phase 2 anomaly detection, this two-tier remains.
- Audit trail in `t_dq_llm_calls` with token counts + latency so cost is observable.
- Informatica has no equivalent. CLAIRE is anomaly/lineage focused, not concept-matching.

### 3.5 Governed exception engine (Step 5)
- Acknowledge accepted violations (legacy data / business rule / in-progress migration / external data provider / other) with optional violation-count ceiling and **mandatory expiry**.
- Issues still persist; raw score still counts them.
- Governed score treats them as PASS up to the ceiling.
- **Both scores rendered** — never hidden.
- Informatica handles this via manual side-channel processes. Suppression decay (auto-expiry) doesn't exist.

---

## 4. Open gaps + roadmap (5 min — be honest)

### Shipped but partial
- **PII anonymizer for LLM prompts** — stubbed as pass-through (Step 6.2). Real implementation pending before any tenant onboarding where column names themselves are sensitive. Logged as IDQP_STATUS open-item #2.
- **Snowflake / BigQuery connectors** — deferred until a real customer asks. Existing 6 dialects cover all current commitments.
- **Score-degradation alerting** — wired into Step 8 when the scheduler lands.

### In flight (Step 6.4–6.8)
- **Excel uploads** — three templates from BRD Tables 11–13 (glossary / business rules / column rules). Easy-path + hard-path split per the plan (see `docs/IDQP_STEP6_PLAN.md`).
- **Proposal review UI** — bulk-approve HIGH, per-row review for MEDIUM/LOW.
- **Rollback** — walks `applied_target_id` in reverse; refuses if `t_dq_issues` references the target.

### Phase 2 (post-Phase-1 ship)
- **Anomaly detection** — Isolation Forest / IQR / z-score numeric, ECOD multivariate, DBSCAN string clustering. Trigger condition: 3+ historical scans per table (baseline window).
- **LLM root-cause + rule suggestion** — feeds the existing proposal queue.
- **Feedback-driven threshold tuning** — score thresholds adjust based on reviewer approve/reject patterns.
- **PySpark backend** — for 10M+ row scans within the NFR-PERF-01 envelope.

### Architectural commitments we will NOT renegotiate
1. Schema isolation in `dq.*`
2. Metadata-only storage (with the documented min/max exception)
3. Dictionary-driven, not column-binding
4. Profile Asset = unit of work
5. Profiler may sample, validator never
6. Two-tier matcher stays

---

## 5. Quick demo-prep checklist

Before the meeting:
- [ ] `docker ps | grep datasharing` → all 7 containers up
- [ ] `ollama list` → `qwen2.5-coder:7b` (or `llama3:latest`) listed
- [ ] `curl localhost:8000/health` → `{"status":"ok"}`
- [ ] Open `localhost:8000/dq` → log in → Profiles list loads (expect 4)
- [ ] Run a fresh scan on profile #18 (holding_snapshots — 862 rows, 9 columns, will show numeric stats well in Tiles view)
- [ ] Pre-warm the LLM with one Draft-with-AI call so the live demo isn't a 30s cold-start

Cred reminders:
- `superadmin@datasharing.local` / `SuperAdmin123!`
- Test connection UUID: `990cd8d7-3951-4a3c-810e-9a987d61ab19` (Postgres on Railway)
