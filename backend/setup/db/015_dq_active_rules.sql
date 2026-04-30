-- 015_dq_active_rules.sql
-- IDQP — Phase 1, Step 3b: materialized rule decisions per (table, column).
--
-- This table is the bridge between the matcher (Step 3b — fuzzy + LLM) and
-- the validator (Step 3c — runs SQL assertions). Each row says:
--   "concept C is bound to column (table, column), at confidence X,
--    awaiting/received human approval Y."
--
-- Source-of-truth tracking:
--   matched_by  = how this row was first proposed (fuzzy | llm | manual)
--   confidence  = the matcher's certainty (high | medium | low)
--   approval_status — the lifecycle:
--     auto_applied = HIGH-confidence match, automatically active (validator runs it)
--     proposed     = MEDIUM/LOW match, awaiting human approval (validator skips)
--     approved     = human approved a proposed match (validator runs it)
--     blocked      = human said "don't run this rule on this column"
--
-- Re-running the matcher upserts: HIGH-confidence rows refresh in place,
-- approved/blocked rows are preserved, lower-confidence stale rows can be
-- safely removed by the matcher (they're proposals, not commitments).

CREATE TABLE IF NOT EXISTS dq.t_dq_active_rules (
    id SERIAL PRIMARY KEY,
    tenant_id     INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    connection_id UUID    NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name   VARCHAR(255) NOT NULL,
    table_name    VARCHAR(255) NOT NULL,
    column_name   VARCHAR(255) NOT NULL,
    concept_id    INTEGER NOT NULL REFERENCES dq.t_dq_concepts(id) ON DELETE CASCADE,

    matched_by    VARCHAR(20) NOT NULL
                  CHECK (matched_by IN ('fuzzy','llm','manual')),
    confidence    VARCHAR(10) NOT NULL
                  CHECK (confidence IN ('high','medium','low')),
    matcher_score NUMERIC(5,4),     -- raw fuzzy ratio or LLM-assigned 0..1
    matcher_reasoning TEXT,         -- human-readable explanation for the UI

    approval_status VARCHAR(20) NOT NULL DEFAULT 'proposed'
                    CHECK (approval_status IN ('auto_applied','proposed','approved','blocked')),
    approved_by   INTEGER REFERENCES public.t_users(id),
    approved_at   TIMESTAMPTZ,
    blocked_reason TEXT,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (connection_id, schema_name, table_name, column_name, concept_id)
);

CREATE INDEX IF NOT EXISTS idx_dq_active_rules_tenant     ON dq.t_dq_active_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_active_rules_target     ON dq.t_dq_active_rules(connection_id, schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_dq_active_rules_status     ON dq.t_dq_active_rules(approval_status);
CREATE INDEX IF NOT EXISTS idx_dq_active_rules_concept    ON dq.t_dq_active_rules(concept_id);

-- ---------------------------------------------------------------------------
-- History — every approval/block change is auditable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_active_rules_hist (
    hist_id SERIAL PRIMARY KEY,
    id              INTEGER NOT NULL,
    tenant_id       INTEGER,
    connection_id   UUID,
    schema_name     VARCHAR(255),
    table_name      VARCHAR(255),
    column_name     VARCHAR(255),
    concept_id      INTEGER,
    matched_by      VARCHAR(20),
    confidence      VARCHAR(10),
    matcher_score   NUMERIC(5,4),
    matcher_reasoning TEXT,
    approval_status VARCHAR(20),
    approved_by     INTEGER,
    approved_at     TIMESTAMPTZ,
    blocked_reason  TEXT,
    created_at      TIMESTAMPTZ,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by      VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_active_rules_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_active_rules_hist (
        id, tenant_id, connection_id, schema_name, table_name, column_name,
        concept_id, matched_by, confidence, matcher_score, matcher_reasoning,
        approval_status, approved_by, approved_at, blocked_reason, created_at,
        changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.connection_id, OLD.schema_name, OLD.table_name,
        OLD.column_name, OLD.concept_id, OLD.matched_by, OLD.confidence,
        OLD.matcher_score, OLD.matcher_reasoning, OLD.approval_status,
        OLD.approved_by, OLD.approved_at, OLD.blocked_reason, OLD.created_at,
        current_user
    );
    -- COALESCE so BEFORE-DELETE doesn't get cancelled by NEW=NULL.
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_active_rules_hist ON dq.t_dq_active_rules;
CREATE TRIGGER trg_dq_active_rules_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_active_rules
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_active_rules_hist();
