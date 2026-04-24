-- 010_brd_compliance.sql
-- Schema additions for BRD items 1, 2, 3, 4, 11, 12, 14, 17.
-- Grouped per BRD item so the intent of each column is readable at a glance.

-- -----------------------------------------------------------------------------
-- Item 2 — Delegation / Out-of-Office (BRD §2.3)
-- Any approver can nominate a colleague for a defined window. Actions taken by
-- the delegate are logged as "on behalf of" the original approver.
-- -----------------------------------------------------------------------------
ALTER TABLE t_users ADD COLUMN delegation_to_user_id INTEGER REFERENCES t_users(id);
ALTER TABLE t_users ADD COLUMN delegation_start TIMESTAMPTZ;
ALTER TABLE t_users ADD COLUMN delegation_end TIMESTAMPTZ;
ALTER TABLE t_users ADD COLUMN delegation_reason VARCHAR(500);

CREATE INDEX idx_users_delegation_window
    ON t_users(delegation_to_user_id, delegation_start, delegation_end)
    WHERE delegation_to_user_id IS NOT NULL;

-- Steps that were acted on by a delegate carry the original approver id so the
-- audit trail can render "Approved by X on behalf of Y" (BRD §2.3).
ALTER TABLE t_workflow_steps ADD COLUMN delegated_from_user_id INTEGER REFERENCES t_users(id);

-- -----------------------------------------------------------------------------
-- Item 3 — Saudi business calendar & public holidays (BRD §4.3)
-- Per-tenant list of non-working calendar days. Weekends (Fri/Sat) are handled
-- by code, not by rows in this table.
-- -----------------------------------------------------------------------------
CREATE TABLE t_business_holidays (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    holiday_date DATE NOT NULL,
    name VARCHAR(255) NOT NULL,
    name_ar VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES t_users(id),
    UNIQUE(tenant_id, holiday_date)
);

CREATE INDEX idx_holidays_tenant_date ON t_business_holidays(tenant_id, holiday_date);

-- -----------------------------------------------------------------------------
-- Item 4 — Escalation ladder (BRD §2.3, EC-05)
-- Day 3 = first breach (already captured by escalated_at).
-- Day 5 = second escalation (Org Admin prompted to reassign).
-- Day 7 = stalled; request must be auto-cancelled if still pending.
-- -----------------------------------------------------------------------------
ALTER TABLE t_workflow_steps ADD COLUMN escalation_level INTEGER NOT NULL DEFAULT 0;
ALTER TABLE t_workflow_steps ADD COLUMN second_escalated_at TIMESTAMPTZ;
ALTER TABLE t_workflow_steps ADD COLUMN stalled_at TIMESTAMPTZ;

-- -----------------------------------------------------------------------------
-- Item 12 — Retention policy (BRD §3.7)
-- Organisation-wide default retention (configurable) and per-file 48h notice
-- flag so we don't spam the pre-expiry email more than once per file.
-- -----------------------------------------------------------------------------
ALTER TABLE t_tenants ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 90
    CHECK (retention_days IN (30, 60, 90, 180));
ALTER TABLE t_tenants_hist ADD COLUMN retention_days INTEGER;

ALTER TABLE t_files ADD COLUMN pre_expiry_notified_at TIMESTAMPTZ;

-- -----------------------------------------------------------------------------
-- Item 14 — Audit export log (BRD §2.2, EC-21)
-- Every export is itself an audit event; we also store a record of each export
-- for downstream review. Export containing personal data is auto-classified.
-- -----------------------------------------------------------------------------
CREATE TABLE t_audit_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES t_tenants(id),
    requested_by INTEGER NOT NULL REFERENCES t_users(id),
    format VARCHAR(20) NOT NULL,
    filters JSONB,
    row_count INTEGER NOT NULL DEFAULT 0,
    contains_personal_data BOOLEAN NOT NULL DEFAULT FALSE,
    classification VARCHAR(50) NOT NULL DEFAULT 'internal',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_exports_tenant ON t_audit_exports(tenant_id, created_at DESC);

-- user_agent is useful forensic context that BRD §8.1 names explicitly.
ALTER TABLE t_audit_events ADD COLUMN actor_user_agent TEXT;

-- -----------------------------------------------------------------------------
-- Item 17 — Platform Admin quotas (BRD §1.3, §2.1 CRITICAL rule)
-- Per-tenant storage and seat caps set at contract time. Vendor can see usage
-- counts, not the data behind them.
-- -----------------------------------------------------------------------------
ALTER TABLE t_tenants ADD COLUMN storage_limit_gb INTEGER;
ALTER TABLE t_tenants ADD COLUMN seat_limit INTEGER;
ALTER TABLE t_tenants_hist ADD COLUMN storage_limit_gb INTEGER;
ALTER TABLE t_tenants_hist ADD COLUMN seat_limit INTEGER;

-- Keep history trigger aligned with the new columns.
CREATE OR REPLACE FUNCTION fn_tenants_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO t_tenants_hist (
        id, name, name_ar, slug, tenant_type, dpo_name, dpo_email, is_active,
        version, retention_days, storage_limit_gb, seat_limit, changed_by
    )
    VALUES (
        OLD.id, OLD.name, OLD.name_ar, OLD.slug, OLD.tenant_type, OLD.dpo_name,
        OLD.dpo_email, OLD.is_active, OLD.version, OLD.retention_days,
        OLD.storage_limit_gb, OLD.seat_limit, current_user
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
