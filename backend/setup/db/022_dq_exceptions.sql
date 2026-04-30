-- 022_dq_exceptions.sql
-- IDQP — Phase 1, Step 5: governed exception engine (BRD §4.8 / FR-EXC).
--
-- An *exception* is a tenant-scoped acknowledgement that a specific active
-- rule's violations are accepted (legacy data, business rule, in-progress
-- onboarding, etc.). Issues still persist — raw_score continues to count
-- them — but governed_score treats them as PASS up to an optional ceiling.
--
-- Lifecycle states:
--   active  → currently in force (and NOT past expires_at)
--   revoked → terminal; reason recorded
--   expired → set by the Step 8 sweeper. Until then, read-time filters
--             treat (active AND expires_at < now()) as if revoked.
--
-- Constraint: at most one ACTIVE exception per active_rule_id (enforced via
-- partial unique index, so the table can still hold revoked-and-replaced
-- history rows for audit).
--
-- Idempotent (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS dq.t_dq_exceptions (
    id SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    profile_id     INTEGER NOT NULL REFERENCES dq.t_dq_profiles(id) ON DELETE CASCADE,
    active_rule_id INTEGER NOT NULL REFERENCES dq.t_dq_active_rules(id) ON DELETE CASCADE,

    -- Why is this rule's failure being suppressed for governance?
    reason_category VARCHAR(40) NOT NULL
        CHECK (reason_category IN (
            'legacy_data',        -- pre-existing rows that pre-date the rule
            'business_accepted',  -- known/approved business behavior
            'in_progress',        -- data still being onboarded / cleaned up
            'data_provider',      -- upstream system limitation we live with
            'other'
        )),
    explanation TEXT NOT NULL,

    -- Suppression envelope.
    --   NULL    = unconditional (every violation is forgiven for governed score)
    --   integer = forgive up to N violations; an overage is treated as raw
    violation_count_ceiling BIGINT,

    status      VARCHAR(20) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','revoked','expired')),
    expires_at  TIMESTAMPTZ NOT NULL,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by    INTEGER REFERENCES public.t_users(id),
    revoked_at    TIMESTAMPTZ,
    revoked_by    INTEGER REFERENCES public.t_users(id),
    revoke_reason TEXT,

    CONSTRAINT chk_exception_ceiling_nonneg
        CHECK (violation_count_ceiling IS NULL OR violation_count_ceiling >= 0)
);

-- One ACTIVE exception per active rule. Replacing an active exception means
-- revoking the old one first.
CREATE UNIQUE INDEX IF NOT EXISTS idx_dq_exc_active_per_rule
    ON dq.t_dq_exceptions(active_rule_id) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_dq_exc_tenant   ON dq.t_dq_exceptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_exc_profile  ON dq.t_dq_exceptions(profile_id);
CREATE INDEX IF NOT EXISTS idx_dq_exc_rule     ON dq.t_dq_exceptions(active_rule_id);
CREATE INDEX IF NOT EXISTS idx_dq_exc_expires  ON dq.t_dq_exceptions(expires_at)
    WHERE status = 'active';

-- ---------------------------------------------------------------------------
-- History — every exception change is auditable. Same shape as
-- t_dq_concepts_hist / t_dq_profiles_hist.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_exceptions_hist (
    hist_id SERIAL PRIMARY KEY,
    id              INTEGER NOT NULL,
    tenant_id       INTEGER,
    profile_id      INTEGER,
    active_rule_id  INTEGER,
    reason_category VARCHAR(40),
    explanation     TEXT,
    violation_count_ceiling BIGINT,
    status          VARCHAR(20),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ,
    created_by      INTEGER,
    revoked_at      TIMESTAMPTZ,
    revoked_by      INTEGER,
    revoke_reason   TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by      VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_exceptions_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_exceptions_hist (
        id, tenant_id, profile_id, active_rule_id,
        reason_category, explanation, violation_count_ceiling,
        status, expires_at,
        created_at, created_by, revoked_at, revoked_by, revoke_reason,
        changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.profile_id, OLD.active_rule_id,
        OLD.reason_category, OLD.explanation, OLD.violation_count_ceiling,
        OLD.status, OLD.expires_at,
        OLD.created_at, OLD.created_by, OLD.revoked_at, OLD.revoked_by, OLD.revoke_reason,
        current_user
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_exceptions_hist ON dq.t_dq_exceptions;
CREATE TRIGGER trg_dq_exceptions_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_exceptions
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_exceptions_hist();
