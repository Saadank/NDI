# IDQP — Step 6 Plan (Excel + LLM SQL Generation)

**Status:** ✅ **All sub-steps complete (2026-05-13)** — see `IDQP_STATUS.md` for the chronological log.
**Last updated:** 2026-05-13.
**Provider used:** local Ollama (`qwen2.5-coder:7b`) — not Anthropic. See architectural decision #10 in `IDQP_STATUS.md`. Migration numbers ended up 024 (not 023 as planned) because 023 was used for the Step 5.5 column-stats fields.

---

## Goals

1. Let clients author DQ rules at three entry points: **interactive NL drafting** in the dictionary, and **Excel uploads** of glossary / business rules / column rules.
2. Quarantine all LLM-touching code in `data_quality/ai/` so the deterministic rule engine stays auditable on its own.
3. Never let an LLM mutate the rule engine directly — humans approve through a proposal queue (or in-modal for inline drafting).
4. Make the **easy path explicit**: when an Excel row already names its table+column, skip column-matching entirely.

## Scope

**In:** Three Excel templates (Tables 11–13), inline NL → concept drafting, LLM column matcher, NL → SQL/regex generator, proposal queue with HIGH bulk-approve / MEDIUM-LOW per-row, versioning + rollback, PII anonymizer, prompt cache, `t_dq_llm_calls` audit.

**Out (deferred):** Phase 2 features (root-cause, anomaly detection, feedback-driven tuning), Snowflake/BigQuery connectors, inline editing of generated SQL with re-validation.

---

## Architecture

Three entry points, one unified promotion path into the deterministic rule engine.

```
                             ┌──────────────────────────────────────────┐
        Approach 2 ─────────▶│  POST /concepts/draft-from-nl            │
        (interactive)        │   user types NL → LLM drafts concept     │
                             │   user reviews in modal → save           │
                             │   ✗ no proposal row (real-time review)   │
                             │   ✓ t_dq_llm_calls audit                 │
                             └────────────────┬─────────────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────────┐
                                    │  t_dq_concepts       │  (deterministic)
                                    │  t_dq_active_rules   │
                                    └──────────────────────┘
                                              ▲
                                              │  apply (post-approval only)
                             ┌────────────────┴─────────────────────────┐
        Approach 1 ─────────▶│  POST /imports (Excel)                   │
        (batch)              │   parse → enrich → propose → review      │
                             │   ✓ t_dq_imports                         │
                             │   ✓ t_dq_proposals (review queue)        │
                             │   ✓ t_dq_llm_calls audit                 │
                             └──────────────────────────────────────────┘

Inside the AI subsystem (both entry points share these):

  excel_parser ─┐
                ├─▶ pii_anonymizer ─▶ ai/client ─▶ Anthropic ─▶ validators ─▶ persist
  nl_endpoint ──┘    (strip raw vals)   (1 place)   (Haiku 4.5)  (schema +
                                                                  SQL safety)
```

**Invariant:** `data_quality/services/`, `repositories/`, `routers/` never import from `data_quality/ai/`. Only the proposal service crosses the boundary, at approval time.

---

## File layout

```
data_quality/
├── ai/
│   ├── __init__.py
│   ├── client.py                          Anthropic client, retry, cache config
│   ├── prompts/
│   │   ├── concept_match.py               (moved from llm_matcher.py)
│   │   ├── column_match.py                term → ranked column candidates
│   │   ├── sql_generation.py              NL rule → rule_type + parameter
│   │   ├── concept_draft.py               NL → full concept (Approach 2)
│   │   └── synonym_expansion.py           concept name → synonyms[]
│   ├── matchers/
│   │   └── llm_column_matcher.py          (uses prompts/concept_match.py)
│   ├── validators/
│   │   ├── response_schema.py             pydantic per-purpose
│   │   ├── sql_safety.py                  sqlglot — SELECT-only, single table, no DDL
│   │   └── rule_type_whitelist.py         only the 5 supported rule_types
│   ├── repositories/
│   │   ├── import_repository.py           t_dq_imports
│   │   ├── glossary_repository.py         t_dq_glossary_terms
│   │   ├── proposal_repository.py         t_dq_proposals
│   │   └── llm_call_repository.py         t_dq_llm_calls
│   ├── services/
│   │   ├── pii_anonymizer.py              gatekeeper — strips raw values
│   │   ├── excel_parser.py                openpyxl, row validation, error report
│   │   ├── glossary_ingest.py             Table 11
│   │   ├── business_rule_ingest.py        Table 12 (easy + hard paths)
│   │   ├── column_rule_ingest.py          Table 13
│   │   ├── concept_draft_service.py       Approach 2 — NL → concept draft
│   │   └── proposal_service.py            apply / reject / rollback (the boundary)
│   └── routers/
│       ├── imports.py                     POST /imports, GET /imports, GET /imports/{id}
│       ├── proposals.py                   GET, POST /{id}/approve, /{id}/reject, bulk
│       └── concepts_ai.py                 POST /concepts/draft-from-nl (Approach 2)
├── enums/                                 unchanged
├── repositories/                          unchanged
├── services/                              unchanged minus llm_matcher.py (moved)
├── routers/                               unchanged
├── workers/                               (Step 8)
├── dependencies.py
└── permissions.py
```

---

## Data model — migration 023

```sql
-- All in dq schema, all tenant-scoped, all with history triggers.

CREATE TABLE dq.t_dq_imports (
  id              SERIAL PRIMARY KEY,
  tenant_id       INT  NOT NULL REFERENCES public.t_tenants(id),
  uploader_id     INT  NOT NULL REFERENCES public.t_users(id),
  kind            TEXT NOT NULL,  -- glossary | business_rules | column_rules
  filename        TEXT NOT NULL,
  file_hash       TEXT NOT NULL,  -- sha256 — idempotency
  status          TEXT NOT NULL,  -- uploaded|parsing|enriching|awaiting_review|applied|rolled_back|error
  row_count       INT  NOT NULL DEFAULT 0,
  error_count     INT  NOT NULL DEFAULT 0,
  errors          JSONB,           -- per-row parse errors
  version_label   TEXT,            -- user-supplied (e.g. "Q2-2026-glossary-v3")
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  applied_at      TIMESTAMPTZ,
  rolled_back_at  TIMESTAMPTZ,
  UNIQUE (tenant_id, file_hash)
);

CREATE TABLE dq.t_dq_glossary_terms (
  id          SERIAL PRIMARY KEY,
  tenant_id   INT  NOT NULL REFERENCES public.t_tenants(id),
  import_id   INT  NOT NULL REFERENCES dq.t_dq_imports(id) ON DELETE CASCADE,
  term        TEXT NOT NULL,
  definition  TEXT,
  synonyms    TEXT[],
  language    TEXT,         -- en | ar | mixed | unknown — helps multilingual matching
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dq.t_dq_proposals (
  id                  SERIAL PRIMARY KEY,
  tenant_id           INT  NOT NULL REFERENCES public.t_tenants(id),
  import_id           INT  REFERENCES dq.t_dq_imports(id) ON DELETE CASCADE,
  source_row          INT,                  -- Excel row number for traceability
  kind                TEXT NOT NULL,        -- new_concept | concept_synonym
                                            -- | active_rule_binding | concept_sql_parameter
  status              TEXT NOT NULL,        -- pending|approved|rejected|superseded
                                            -- |rolled_back|error|unsupported_logic
                                            -- |rejected_by_validator|needs_llm
  confidence          TEXT,                 -- HIGH | MEDIUM | LOW
  payload             JSONB NOT NULL,       -- kind-specific (see below)
  candidates          JSONB,                -- for column_match: ranked alternatives
  proposed_value      JSONB,                -- what LLM returned, raw
  final_value         JSONB,                -- what reviewer accepted (may differ)
  reasoning           TEXT,                 -- LLM's one-line justification
  error_reason        TEXT,                 -- if rejected_by_validator / unsupported_logic
  target_concept_id   INT  REFERENCES dq.t_dq_concepts(id),
  applied_target_id   INT,                  -- id in concepts or active_rules table after apply
  applied_target_kind TEXT,                 -- concept | active_rule
  reviewer_id         INT  REFERENCES public.t_users(id),
  reviewed_at         TIMESTAMPTZ,
  llm_call_id         INT  REFERENCES dq.t_dq_llm_calls(id),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON dq.t_dq_proposals (import_id, status, confidence);

CREATE TABLE dq.t_dq_llm_calls (
  id                    SERIAL PRIMARY KEY,
  tenant_id             INT  NOT NULL REFERENCES public.t_tenants(id),
  purpose               TEXT NOT NULL,  -- concept_match | column_match
                                        -- | sql_generation | concept_draft | synonym_expansion
  model                 TEXT NOT NULL,
  prompt_version        INT  NOT NULL,
  input_tokens          INT,
  cache_read_tokens     INT,
  cache_creation_tokens INT,
  output_tokens         INT,
  latency_ms            INT,
  status                TEXT NOT NULL,  -- ok | timeout | api_error | parse_error | validator_failed
  error                 TEXT,
  prompt_hash           TEXT,           -- sha256 of fully-rendered prompt (without raw vals)
  response_hash         TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON dq.t_dq_llm_calls (tenant_id, created_at DESC);
CREATE INDEX ON dq.t_dq_llm_calls (purpose, status);
```

**Proposal `payload` shapes by kind:**

| kind | payload |
|---|---|
| `new_concept` | `{ name, dimension, rule_type, parameter, severity, synonyms[], applies_to_types[] }` |
| `concept_synonym` | `{ concept_id, new_synonyms[] }` |
| `active_rule_binding` | `{ profile_id, column_name, concept_id }` |
| `concept_sql_parameter` | `{ concept_id, rule_type, parameter }` (LLM-updated parameter for an existing concept) |

---

## Excel templates (BRD Tables 11–13)

**Table 11 — Business Glossary** (`kind=glossary`)
```
term* | definition | synonyms (semicolon-sep) | language (en|ar|mixed|auto)
```
*= required. **No LLM calls** — pure parse + persist + reviewer maps to existing concepts.

**Table 12 — Business Rules** (`kind=business_rules`)
```
rule_name* | description | logic_nl* | severity* | dimension* | table | column
```
**Easy path:** `table` + `column` filled → skip column matching, only call `sql_generation`.
**Hard path:** `column` empty → call `column_match` first (using the glossary already imported as context), then `sql_generation` per matched column.
Out-of-band logic (e.g. cross-table joins) → proposal `status=unsupported_logic`.

**Table 13 — DQ Column Rules** (`kind=column_rules`)
```
table* | column* | rule_type* | parameter | severity* | dimension*
```
Always specifies columns. **No LLM calls** if `parameter` is supplied; if `parameter` is blank and `rule_type=format_regex`, call `sql_generation` for just the regex.

---

## LLM purposes (5 prompt modules)

| Purpose | Inputs | Output | Where used |
|---|---|---|---|
| `concept_match` | column metadata + dictionary | `[{concept_id, confidence, reasoning}]` | existing matcher (moved to ai/) |
| `column_match` | business term + column list (one profile or whole schema) | `[{column_name, confidence, reasoning}]` ranked | Table 12 hard path |
| `sql_generation` | NL rule + target column metadata | `{rule_type, parameter, confidence, reasoning}` or `{rule_type: null, error_reason}` | Tables 12/13 |
| `concept_draft` | NL text + dimension hint | `{name, rule_type, parameter, severity, synonyms[], applies_to_types[], confidence, reasoning}` | Approach 2 |
| `synonym_expansion` | concept name + 2-3 examples | `[synonyms]` (capped at 10) | Approach 2, glossary ingest |

All prompts share: **multilingual instruction** ("column names may be in any language including Arabic; consider transliteration"), **bounded rule_type whitelist**, **JSON-only output**, **conservative confidence** ("HIGH only when unambiguous").

**Batching policy:**
- `column_match` batches: one call per ≤50 terms × ≤30 columns. Column list is cached.
- `sql_generation`: one call per rule (rule-specific context, no batching benefit).
- `concept_match`: one call per column (existing behavior).

---

## Validators

Every LLM response passes through:
1. `response_schema.py` — pydantic check against the purpose's expected shape.
2. `rule_type_whitelist.py` — only `{not_null, max_null_rate, no_pseudo_nulls, unique, format_regex}` allowed.
3. `sql_safety.py` (only when `parameter` is a SQL fragment) — sqlglot parse, must be SELECT-only on the named table, no `;`, no comments, no DDL/DML keywords, no joins outside the target table.

Failure → `proposal.status='rejected_by_validator'`, `error_reason` set, never reaches the reviewer as approvable.

---

## API surface

```
POST   /imports                               (multipart upload + kind + version_label)
GET    /imports                               (list, filter by status / kind)
GET    /imports/{id}                          (status, errors, proposal counts)
POST   /imports/{id}/rollback

GET    /proposals                             (filter by import_id, status, confidence, kind)
GET    /proposals/{id}                        (full payload + candidates)
POST   /proposals/{id}/approve                (optional final_value override)
POST   /proposals/{id}/reject                 (with reason)
POST   /proposals/bulk-approve                (filter: import_id + confidence=HIGH)

POST   /concepts/draft-from-nl                (Approach 2 — body: { text, dimension? })
POST   /concepts/{id}/expand-synonyms         (Approach 2 — uses synonym_expansion)
```

All gated by `require_data_quality`. Mutations require `dq_admin` role (defer to existing `permissions.py`).

---

## UI plan (`frontend/dq.html`)

**New top-level tab: Imports.** List of uploads with status badges, click → import detail view with: row breakdown, error report, proposal queue filtered to that import. Buttons: "Bulk-approve HIGH", "Apply approved", "Rollback".

**Dictionary tab gets a "Draft with AI" button** next to "+ New concept". Opens a modal: textarea for NL, dimension dropdown, "Draft" button → shows the LLM proposal pre-filled into the existing new-concept form for editing → Save commits.

**Proposal review modal** (per-row): shows the source Excel row, the LLM proposal, alternative candidates if `column_match` produced more than one, reasoning, override fields, Approve / Reject buttons.

---

## Sub-step sequencing

| # | What lands | Why |
|---|---|---|
| **6.0** | **Refactor**: create `ai/` subpackage, move `llm_matcher.py` → `ai/matchers/`, update `active_rule_service.py` import. **No behavior change.** Single commit. | Clean baseline before any new code. |
| **6.1** | Migration 023 + repos (`import`, `glossary`, `proposal`, `llm_call`). | Tables exist before services need them. |
| **6.2** | Shared infra: `ai/client.py`, `ai/prompts/__init__.py` framework, `pii_anonymizer.py`, `validators/`. | Foundation everything else uses. |
| **6.3** | **Approach 2 end-to-end**: `concept_draft.py` prompt, `concept_draft_service.py`, `POST /concepts/draft-from-nl`, Dictionary "Draft with AI" modal. | Smallest E2E LLM path — validates client + prompts + validators + audit before tackling Excel. |
| **6.4** | Excel parser + Table 11 (glossary) ingest. **No LLM calls** here. | Cheapest Excel path; proves the parser + import lifecycle. |
| **6.5** | Table 13 (column rules) ingest, easy path only. Triggers `sql_generation` when `parameter` is blank. | Adds one LLM purpose; columns are already specified so no `column_match` needed. |
| **6.6** | Table 12 (business rules) ingest, **both easy and hard paths**. Adds `column_match`. | Hardest case — all infra now proven. |
| **6.7** | Proposal review UI: list, per-row modal, bulk-approve HIGH, apply. | Hooks the queue to humans. |
| **6.8** | Rollback: walks `applied_target_id` in reverse, refuses if `t_dq_issues` references the target. | Last because it's the safety net for everything above. |

Each sub-step is independently committable. Total: ~8 commits.

---

## Resolved design decisions

1. **Inline drafts (Approach 2) bypass `t_dq_proposals`.** The user IS the reviewer in real-time. We still record `t_dq_llm_calls` for cost/audit. Tradeoff: we lose audit-of-corrections data for inline drafts.
2. **Table 12 `unsupported_logic` proposals stay visible to reviewers.** They can convert to a manual rule (paste their own SQL into `parameter`) — better than silently dropping the rule.
3. **Re-uploads with edited rows are accepted as new imports.** `version_label` is the diff. The `UNIQUE(tenant_id, file_hash)` only blocks byte-identical re-uploads.
4. **Reviewer override on HIGH:** column override allowed; rule_type override not (whitelist enforced server-side regardless of confidence).
5. **Cost cap:** uploads estimating > some token threshold require admin confirmation. Estimated tokens shown in upload preview before enrichment kicks off. Threshold TBD — start at 500K tokens.
6. **`pii_anonymizer` enforcement is unit-tested.** Fixture of real-looking row values; CI fails if any raw value reaches a prompt builder's output.

---

## Multilingual / Arabic — design note

**Hardest matching case:** business term "Arabic name" → column `A_name` / `name_ar` / `الاسم`. Levenshtein and token-overlap fail; this is exactly what the LLM matcher exists for.

- The `column_match` prompt explicitly says "column names may be in any language; consider transliteration and abbreviation."
- All matches return **ranked candidates with confidence**, not just top-1. Reviewer picks.
- HIGH = clear single winner. MEDIUM = multiple plausible, one obvious. LOW = uncertain — surface for review.
- UTF-8 throughout (Postgres default — already verified). Arabic column names persist correctly.

---

## Open items still to decide during implementation

- Exact token-cost threshold for admin confirmation on bulk uploads.
- Whether to allow `concept_sql_parameter` proposals to update concepts that already have a parameter (i.e. LLM-rewriting existing rules) or restrict to concepts with `parameter IS NULL`. Lean toward restricted — concept rewriting is a Phase 2 problem.
- Whether `synonym_expansion` runs automatically on every new concept or only on user request. Lean toward request-only to keep cost predictable.
