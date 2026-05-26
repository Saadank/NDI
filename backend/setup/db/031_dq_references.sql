-- 031_dq_references.sql
-- IDQP — Reference data for validity rules.
--
-- A "reference" is a reusable named list of allowed values (e.g. "Saudi
-- Banks", "GCC Countries", "ISO 4217 Currencies"). One reference can be
-- pointed at by many dictionary_match concepts — so the same Saudi-banks
-- list powers rules on bank_name, issuing_bank, payee_bank, etc. without
-- duplicating the list.
--
-- Replaces the inline {values: [...]} parameter shape introduced in 030.
-- After this migration, dictionary_match concepts carry
--   parameter = {"reference_id": N}
-- and the validator fetches values from t_dq_reference_values at scan time.

-- ---------------------------------------------------------------------------
-- 1. References — the named lists themselves.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_references (
    id SERIAL PRIMARY KEY,
    tenant_id        INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,

    -- Human-readable name (e.g. "Saudi Banks"). Unique per tenant so the
    -- concept editor's dropdown stays unambiguous.
    name             VARCHAR(120) NOT NULL,
    description      TEXT,

    -- When TRUE, validator compares values exactly (e.g. ISO 4217 mandates
    -- uppercase). When FALSE (default), matching is case-insensitive and
    -- whitespace is trimmed on both sides — what users want for bank/city
    -- names where "Riyadh", "riyadh", and " RIYADH" should all match.
    case_sensitive   BOOLEAN NOT NULL DEFAULT FALSE,

    is_seed          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by       INTEGER REFERENCES public.t_users(id),

    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_dq_references_tenant ON dq.t_dq_references(tenant_id);

-- ---------------------------------------------------------------------------
-- 2. Reference values — one row per allowed entry.
--
-- Storing values as rows (not a JSONB array on the parent) keeps individual
-- value CRUD trivial — add/remove a single bank without rewriting the whole
-- list — and lets the validator's IN-clause query work straight off an
-- indexed table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_reference_values (
    id SERIAL PRIMARY KEY,
    reference_id     INTEGER NOT NULL REFERENCES dq.t_dq_references(id) ON DELETE CASCADE,
    value            VARCHAR(200) NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (reference_id, value)
);

CREATE INDEX IF NOT EXISTS idx_dq_reference_values_ref ON dq.t_dq_reference_values(reference_id);

-- ---------------------------------------------------------------------------
-- 3. History table — every reference change is auditable, same pattern as
--    t_dq_concepts_hist. We only track the parent reference's metadata;
--    individual value churn would balloon the history without much value,
--    so the values table is not historised.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_references_hist (
    hist_id SERIAL PRIMARY KEY,
    id               INTEGER NOT NULL,
    tenant_id        INTEGER,
    name             VARCHAR(120),
    description      TEXT,
    case_sensitive   BOOLEAN,
    is_seed          BOOLEAN,
    created_at       TIMESTAMPTZ,
    created_by       INTEGER,
    changed_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by       VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_references_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_references_hist (
        id, tenant_id, name, description, case_sensitive, is_seed,
        created_at, created_by, changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.name, OLD.description,
        OLD.case_sensitive, OLD.is_seed,
        OLD.created_at, OLD.created_by, current_user
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_references_hist ON dq.t_dq_references;
CREATE TRIGGER trg_dq_references_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_references
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_references_hist();
