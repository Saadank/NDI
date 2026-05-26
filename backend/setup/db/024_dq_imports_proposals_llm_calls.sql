-- 024_dq_imports_proposals_llm_calls.sql
-- IDQP — Phase 1, Step 6: Excel uploads + LLM-assisted concept drafting.
--
-- Four new tables wire up the LLM-touching workflows without giving the
-- LLM direct write access to the deterministic rule engine. Humans
-- approve through t_dq_proposals; t_dq_llm_calls is the audit trail.
--
-- Tables
--   t_dq_imports          — one row per Excel upload (status machine)
--   t_dq_glossary_terms   — Table 11 rows (business terms + synonyms)
--   t_dq_proposals        — LLM-generated changes awaiting human review
--   t_dq_llm_calls        — full audit of every LLM round-trip
--
-- All tenant-scoped. All idempotent (CREATE TABLE IF NOT EXISTS).

-- ============================================================================
-- t_dq_imports
-- ============================================================================
CREATE TABLE IF NOT EXISTS dq.t_dq_imports (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    uploader_id     INTEGER NOT NULL REFERENCES public.t_users(id),

    kind            VARCHAR(40) NOT NULL
                    CHECK (kind IN ('glossary', 'business_rules', 'column_rules')),

    filename        VARCHAR(500) NOT NULL,
    file_hash       VARCHAR(64)  NOT NULL,  -- sha256 — idempotency

    status          VARCHAR(40)  NOT NULL DEFAULT 'uploaded'
                    CHECK (status IN (
                        'uploaded', 'parsing', 'enriching',
                        'awaiting_review', 'applied',
                        'rolled_back', 'error'
                    )),

    row_count       INTEGER NOT NULL DEFAULT 0,
    error_count     INTEGER NOT NULL DEFAULT 0,
    errors          JSONB,                  -- per-row parse errors

    version_label   VARCHAR(120),            -- e.g. "Q2-2026-glossary-v3"

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at      TIMESTAMPTZ,
    rolled_back_at  TIMESTAMPTZ,

    UNIQUE (tenant_id, file_hash)
);

CREATE INDEX IF NOT EXISTS idx_dq_imports_tenant      ON dq.t_dq_imports(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_imports_status      ON dq.t_dq_imports(status);
CREATE INDEX IF NOT EXISTS idx_dq_imports_created_at  ON dq.t_dq_imports(created_at DESC);

COMMENT ON TABLE dq.t_dq_imports IS
    'One row per Excel upload (Tables 11/12/13). Status machine drives the
     uploaded -> parsing -> enriching -> awaiting_review -> applied lifecycle.
     UNIQUE(tenant_id, file_hash) blocks accidental re-uploads of the same
     byte-identical file; intentional re-uploads use version_label as the
     diff key.';

-- ============================================================================
-- t_dq_glossary_terms
-- ============================================================================
CREATE TABLE IF NOT EXISTS dq.t_dq_glossary_terms (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    import_id   INTEGER NOT NULL REFERENCES dq.t_dq_imports(id)  ON DELETE CASCADE,

    term        VARCHAR(255) NOT NULL,
    definition  TEXT,
    synonyms    TEXT[],
    language    VARCHAR(20),                 -- en | ar | mixed | unknown

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dq_glossary_tenant_term
    ON dq.t_dq_glossary_terms(tenant_id, term);
CREATE INDEX IF NOT EXISTS idx_dq_glossary_import
    ON dq.t_dq_glossary_terms(import_id);

COMMENT ON TABLE dq.t_dq_glossary_terms IS
    'Business-glossary rows (BRD Table 11). Read by column_match to
     enrich its context with tenant-specific terminology.';

-- ============================================================================
-- t_dq_llm_calls — audit trail, written before t_dq_proposals can reference it
-- ============================================================================
CREATE TABLE IF NOT EXISTS dq.t_dq_llm_calls (
    id                    SERIAL PRIMARY KEY,
    tenant_id             INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,

    purpose               VARCHAR(40) NOT NULL
                          CHECK (purpose IN (
                              'concept_match', 'column_match',
                              'sql_generation', 'concept_draft',
                              'synonym_expansion'
                          )),

    model                 VARCHAR(120) NOT NULL,
    prompt_version        INTEGER NOT NULL,

    input_tokens          INTEGER,
    output_tokens         INTEGER,
    -- Anthropic-specific. Always NULL for Ollama-era rows; kept on the
    -- schema so a future provider swap doesn't require a migration.
    cache_read_tokens     INTEGER,
    cache_creation_tokens INTEGER,

    latency_ms            INTEGER,

    status                VARCHAR(40) NOT NULL
                          CHECK (status IN (
                              'ok', 'timeout', 'api_error',
                              'parse_error', 'validator_failed'
                          )),
    error                 TEXT,

    prompt_hash           VARCHAR(64),       -- sha256 of fully-rendered prompt
    response_hash         VARCHAR(64),

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dq_llm_calls_tenant_time
    ON dq.t_dq_llm_calls(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dq_llm_calls_purpose_status
    ON dq.t_dq_llm_calls(purpose, status);

COMMENT ON TABLE dq.t_dq_llm_calls IS
    'Audit of every LLM round-trip. Stores token counts, latency, status,
     and content hashes — never the raw prompt or response (no row values
     can leak into this table since the PII anonymizer runs before the
     hash is computed).';

-- ============================================================================
-- t_dq_proposals
-- ============================================================================
CREATE TABLE IF NOT EXISTS dq.t_dq_proposals (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    import_id           INTEGER REFERENCES dq.t_dq_imports(id) ON DELETE CASCADE,
    -- Excel row number for traceability. NULL for inline-drafted concepts
    -- (Approach 2) which don't come from a file row.
    source_row          INTEGER,

    kind                VARCHAR(40) NOT NULL
                        CHECK (kind IN (
                            'new_concept',
                            'concept_synonym',
                            'active_rule_binding',
                            'concept_sql_parameter'
                        )),

    status              VARCHAR(40) NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending', 'approved', 'rejected',
                            'superseded', 'rolled_back', 'error',
                            'unsupported_logic', 'rejected_by_validator',
                            'needs_llm'
                        )),
    confidence          VARCHAR(10)
                        CHECK (confidence IS NULL OR confidence IN ('HIGH','MEDIUM','LOW')),

    payload             JSONB NOT NULL,        -- kind-specific shape
    candidates          JSONB,                 -- for column_match: ranked alternatives
    proposed_value      JSONB,                 -- LLM's raw return
    final_value         JSONB,                 -- reviewer's accepted value
    reasoning           TEXT,
    error_reason        TEXT,

    target_concept_id   INTEGER REFERENCES dq.t_dq_concepts(id),
    applied_target_id   INTEGER,               -- concept or active_rule id after apply
    applied_target_kind VARCHAR(20)
                        CHECK (applied_target_kind IS NULL OR applied_target_kind IN ('concept','active_rule')),

    reviewer_id         INTEGER REFERENCES public.t_users(id),
    reviewed_at         TIMESTAMPTZ,

    llm_call_id         INTEGER REFERENCES dq.t_dq_llm_calls(id),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dq_proposals_tenant
    ON dq.t_dq_proposals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_proposals_import_status_conf
    ON dq.t_dq_proposals(import_id, status, confidence);
CREATE INDEX IF NOT EXISTS idx_dq_proposals_status_created
    ON dq.t_dq_proposals(status, created_at DESC);

COMMENT ON TABLE dq.t_dq_proposals IS
    'LLM-generated changes awaiting human approval. Status transitions are
     one-way except superseded (later import overrides earlier). Rollback
     walks applied_target_id back through this table in reverse order.';
