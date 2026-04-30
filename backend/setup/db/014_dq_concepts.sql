-- 014_dq_concepts.sql
-- IDQP — Phase 1, Step 3a: dictionary that drives rule applicability.
--
-- The dictionary replaces the BRD's naive "apply rule X to all string columns"
-- approach with a smarter model: each concept declares the column-name
-- synonyms it answers to, the rule it implies, and the semantic types it
-- applies on. A column's name is matched against the dictionary (Step 3b)
-- and the resulting rules execute during scans (Step 3c).
--
-- Phase 1 scope: completeness + validity + uniqueness only. Consistency,
-- timeliness, accuracy come back when rule libraries for those dimensions
-- are designed.
--
-- Per-tenant: each tenant has its own editable copy of the dictionary.
-- Defaults are seeded at runtime via POST /concepts/seed-defaults so new
-- tenants pick them up on first use.

CREATE TABLE IF NOT EXISTS dq.t_dq_concepts (
    id SERIAL PRIMARY KEY,
    tenant_id        INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,

    -- "What kind of quality problem does this concept guard against?"
    -- Phase 1: completeness / validity / uniqueness only.
    dimension        VARCHAR(20) NOT NULL
                     CHECK (dimension IN ('completeness','validity','uniqueness')),

    -- Stable internal identifier within the dimension. Lower-snake-case.
    concept          VARCHAR(100) NOT NULL,

    -- Column-name synonyms a column can match on. Stored as text[] so the
    -- matcher can compare the column name against each entry directly. All
    -- entries are normalized lowercase at insert time.
    synonyms         TEXT[] NOT NULL DEFAULT '{}',

    -- What rule fires when a column matches this concept.
    rule_type        VARCHAR(40) NOT NULL
                     CHECK (rule_type IN
                            ('not_null','max_null_rate','no_pseudo_nulls',
                             'unique','format_regex')),

    -- Rule-specific knob: regex string, threshold value, etc. Schema-less so
    -- adding rule_types in Step 3c doesn't require another migration.
    parameter        JSONB NOT NULL DEFAULT '{}',

    severity         VARCHAR(20) NOT NULL DEFAULT 'medium'
                     CHECK (severity IN ('critical','high','medium','low')),

    -- NULL = applies to columns of any semantic type. Otherwise the matcher
    -- only proposes this concept when the table's semantic type is in the list.
    applies_to_types VARCHAR(50)[],

    notes            TEXT,
    enabled          BOOLEAN NOT NULL DEFAULT TRUE,

    -- Tracks whether this row was seeded by the platform defaults; the seed
    -- endpoint uses this to skip re-seeding rows the user has already edited.
    is_seed          BOOLEAN NOT NULL DEFAULT FALSE,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by       INTEGER REFERENCES public.t_users(id),

    UNIQUE (tenant_id, dimension, concept)
);

CREATE INDEX IF NOT EXISTS idx_dq_concepts_tenant     ON dq.t_dq_concepts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_concepts_dimension  ON dq.t_dq_concepts(dimension);
CREATE INDEX IF NOT EXISTS idx_dq_concepts_enabled    ON dq.t_dq_concepts(enabled);
-- GIN index for fast synonym lookup once the matcher (Step 3b) is wired in.
CREATE INDEX IF NOT EXISTS idx_dq_concepts_synonyms   ON dq.t_dq_concepts USING GIN(synonyms);

-- ---------------------------------------------------------------------------
-- History table — every dictionary change is auditable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_concepts_hist (
    hist_id SERIAL PRIMARY KEY,
    id               INTEGER NOT NULL,
    tenant_id        INTEGER,
    dimension        VARCHAR(20),
    concept          VARCHAR(100),
    synonyms         TEXT[],
    rule_type        VARCHAR(40),
    parameter        JSONB,
    severity         VARCHAR(20),
    applies_to_types VARCHAR(50)[],
    notes            TEXT,
    enabled          BOOLEAN,
    is_seed          BOOLEAN,
    created_at       TIMESTAMPTZ,
    created_by       INTEGER,
    changed_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by       VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_concepts_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_concepts_hist (
        id, tenant_id, dimension, concept, synonyms, rule_type, parameter,
        severity, applies_to_types, notes, enabled, is_seed,
        created_at, created_by, changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.dimension, OLD.concept, OLD.synonyms,
        OLD.rule_type, OLD.parameter, OLD.severity, OLD.applies_to_types,
        OLD.notes, OLD.enabled, OLD.is_seed,
        OLD.created_at, OLD.created_by, current_user
    );
    -- BEFORE UPDATE OR DELETE: NEW is NULL on DELETE, so returning NEW would
    -- silently abort the delete. COALESCE keeps both paths working.
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_concepts_hist ON dq.t_dq_concepts;
CREATE TRIGGER trg_dq_concepts_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_concepts
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_concepts_hist();
