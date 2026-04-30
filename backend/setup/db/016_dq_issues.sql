-- 016_dq_issues.sql
-- IDQP — Phase 1, Step 3c: validator output.
--
-- One row per (scan, active_rule). Each scan re-evaluates every active rule
-- on the target table, producing a new issue row with the violation count
-- and pass/fail status. History = the table itself (per-scan immutable).
--
-- Privacy: no raw offending row values are stored. violation_patterns holds
-- *pattern signatures* of violators (counts only) so users can see the shape
-- of the bad data without leaking it.

CREATE TABLE IF NOT EXISTS dq.t_dq_issues (
    id SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,
    scan_id        INTEGER NOT NULL REFERENCES dq.t_dq_scans(id) ON DELETE CASCADE,
    connection_id  UUID    NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name    VARCHAR(255) NOT NULL,
    table_name     VARCHAR(255) NOT NULL,
    column_name    VARCHAR(255) NOT NULL,

    active_rule_id INTEGER NOT NULL REFERENCES dq.t_dq_active_rules(id) ON DELETE CASCADE,
    concept_id     INTEGER NOT NULL REFERENCES dq.t_dq_concepts(id),

    -- Denormalized for fast filter/aggregate without an extra join.
    dimension  VARCHAR(20) NOT NULL
               CHECK (dimension IN ('completeness','validity','uniqueness')),
    rule_type  VARCHAR(40) NOT NULL,
    severity   VARCHAR(20) NOT NULL
               CHECK (severity IN ('critical','high','medium','low')),

    -- The measurement.
    row_count        BIGINT,           -- total rows considered
    violation_count  BIGINT,           -- offending rows
    violation_rate   NUMERIC(6, 5),

    -- Did the rule fire?
    --   pass  = no violations / threshold not exceeded
    --   fail  = violations found / threshold exceeded
    --   error = SQL execution failed (not a rule violation)
    status         VARCHAR(20) NOT NULL
                   CHECK (status IN ('pass','fail','error')),
    error_message  TEXT,

    -- Snapshot of the rule parameter used (so historical rows stay readable
    -- after a concept's parameter is edited).
    rule_parameter JSONB,

    -- Pattern-signature distribution among violators. Counts only — no values.
    violation_patterns JSONB,

    -- Diagnostics fed back to the UI (e.g. "null_rate=0.12 exceeds 0.05").
    diagnostic_text TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (scan_id, active_rule_id)
);

CREATE INDEX IF NOT EXISTS idx_dq_issues_tenant     ON dq.t_dq_issues(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_issues_scan       ON dq.t_dq_issues(scan_id);
CREATE INDEX IF NOT EXISTS idx_dq_issues_target     ON dq.t_dq_issues(connection_id, schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_dq_issues_status     ON dq.t_dq_issues(status);
CREATE INDEX IF NOT EXISTS idx_dq_issues_dimension  ON dq.t_dq_issues(dimension);
CREATE INDEX IF NOT EXISTS idx_dq_issues_severity   ON dq.t_dq_issues(severity);
CREATE INDEX IF NOT EXISTS idx_dq_issues_active_rule ON dq.t_dq_issues(active_rule_id);
