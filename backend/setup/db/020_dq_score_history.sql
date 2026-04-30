-- 020_dq_score_history.sql
-- IDQP — Phase 1, Step 4: per-(profile, scan, dimension) quality scores.
--
-- Each successful scan emits one score row per dimension (completeness /
-- validity / uniqueness) plus one 'overall' aggregate row. The validator
-- computes pass_rate per issue (1 - violation_rate); we average those across
-- the dimension and band the result into a tier (good / acceptable /
-- not_acceptable) using the per-tenant thresholds in t_dq_score_thresholds.
--
-- Trend deltas (↑ ↓ =) are computed at read time with LAG() over scan_id.
--
-- Idempotent (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS dq.t_dq_score_history (
    id SERIAL PRIMARY KEY,
    tenant_id  INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES dq.t_dq_profiles(id) ON DELETE CASCADE,
    scan_id    INTEGER NOT NULL REFERENCES dq.t_dq_scans(id) ON DELETE CASCADE,

    -- Future-proofing: when Step 5 adds governed/exception scopes we'll have
    -- separate rows per scope. For Phase 1 this is always ('profile','').
    scope_type VARCHAR(20) NOT NULL DEFAULT 'profile'
               CHECK (scope_type IN ('profile','schema','tenant','column')),
    scope_key  VARCHAR(255) NOT NULL DEFAULT '',

    -- 'overall' aggregates pass_rate across every issue in the scan.
    dimension  VARCHAR(20) NOT NULL
               CHECK (dimension IN ('completeness','validity','uniqueness','overall')),

    -- 0.0–1.0 share of rule executions that passed.
    pass_rate    NUMERIC(6, 5) NOT NULL,
    rule_count   INTEGER NOT NULL DEFAULT 0,
    pass_count   INTEGER NOT NULL DEFAULT 0,
    fail_count   INTEGER NOT NULL DEFAULT 0,
    error_count  INTEGER NOT NULL DEFAULT 0,

    -- 'raw' = unweighted average. 'governed' is reserved for Step 5
    -- (raw minus exception-suppressed issues). For Phase 1 they're equal.
    raw_score      NUMERIC(6, 5) NOT NULL,
    governed_score NUMERIC(6, 5) NOT NULL,

    tier VARCHAR(20) NOT NULL
         CHECK (tier IN ('good','acceptable','not_acceptable','no_rules')),

    -- Snapshot of the threshold config used to band this row, so historical
    -- tiers stay stable when an admin retunes the thresholds later.
    thresholds_snapshot JSONB,

    -- Optional severity-weighted score variant. NULL when severity weighting
    -- was off at scan time (the default for Phase 1).
    weighted_score NUMERIC(6, 5),

    computed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (scan_id, scope_type, scope_key, dimension)
);

CREATE INDEX IF NOT EXISTS idx_dq_score_hist_tenant       ON dq.t_dq_score_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_score_hist_profile      ON dq.t_dq_score_history(profile_id);
CREATE INDEX IF NOT EXISTS idx_dq_score_hist_scan         ON dq.t_dq_score_history(scan_id);
CREATE INDEX IF NOT EXISTS idx_dq_score_hist_profile_dim  ON dq.t_dq_score_history(profile_id, dimension, scan_id DESC);
