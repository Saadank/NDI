-- 021_dq_score_thresholds.sql
-- IDQP — Phase 1, Step 4: per-tenant tier thresholds.
--
-- A pass_rate at or above good_min lands in the 'good' band, at or above
-- acceptable_min lands in 'acceptable', else 'not_acceptable'. Defaults
-- mirror the BRD §4.7 numbers (95% / 70%) and apply tenant-wide unless a
-- per-dimension row overrides them.
--
-- Severity weighting is opt-in per tenant. When ON, each rule contributes
-- pass_rate × severity_weight (critical=4, high=3, medium=2, low=1) to a
-- weighted_score column on score_history; raw_score remains unweighted.
--
-- Idempotent (CREATE TABLE IF NOT EXISTS + ON CONFLICT seed).

CREATE TABLE IF NOT EXISTS dq.t_dq_score_thresholds (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,

    -- '*' = default for every dimension; specific dimension rows override.
    dimension VARCHAR(20) NOT NULL DEFAULT '*'
              CHECK (dimension IN ('*','completeness','validity','uniqueness','overall')),

    good_min       NUMERIC(4, 3) NOT NULL DEFAULT 0.950,
    acceptable_min NUMERIC(4, 3) NOT NULL DEFAULT 0.700,

    severity_weighting_enabled BOOLEAN NOT NULL DEFAULT FALSE,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES public.t_users(id),

    CONSTRAINT chk_threshold_order CHECK (good_min >= acceptable_min),
    CONSTRAINT chk_threshold_range
        CHECK (good_min BETWEEN 0 AND 1 AND acceptable_min BETWEEN 0 AND 1),

    UNIQUE (tenant_id, dimension)
);

CREATE INDEX IF NOT EXISTS idx_dq_score_thresholds_tenant
    ON dq.t_dq_score_thresholds(tenant_id);

-- Seed a default '*' row for every existing tenant. New tenants get the same
-- defaults the first time they hit the read path (service falls back when no
-- row exists), so no trigger / data-fixup is needed for tenants created later.
INSERT INTO dq.t_dq_score_thresholds (tenant_id, dimension, good_min, acceptable_min)
SELECT id, '*', 0.950, 0.700 FROM public.t_tenants
ON CONFLICT (tenant_id, dimension) DO NOTHING;
