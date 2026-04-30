-- 012_dq_profiler.sql
-- Intelligent Data Quality Platform (IDQP) — Phase 1, Step 2
-- Statistical profiler: scans + per-column profile snapshots (BRD §4.5, FR-PROF).
--
-- A *scan* = one descriptive pass over a (connection, schema, table). Each
-- scan emits one row per column in t_dq_column_profiles. Phase 1 keeps the
-- profile descriptive only — anomaly logic / baselines arrive in Phase 2.
--
-- Idempotent (CREATE TABLE IF NOT EXISTS); safe to re-run.

-- ---------------------------------------------------------------------------
-- dq.t_dq_scans — one row per scan execution.
--
-- A scan starts in 'pending', flips to 'running' when the worker picks it up,
-- and settles in 'success' or 'failed'. Manual scans live alongside scheduled
-- scans (added in Step 8) — `triggered_by` distinguishes them.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_scans (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES public.t_tenants(id),
    connection_id   UUID    NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name     VARCHAR(255) NOT NULL,
    table_name      VARCHAR(255) NOT NULL,
    scan_type       VARCHAR(20)  NOT NULL DEFAULT 'profile'
                    CHECK (scan_type IN ('profile','validation','full')),
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','success','failed','cancelled')),
    triggered_by    INTEGER REFERENCES public.t_users(id),  -- NULL = scheduler
    trigger_source  VARCHAR(20) NOT NULL DEFAULT 'manual'
                    CHECK (trigger_source IN ('manual','schedule','retry','api')),
    row_count       BIGINT,
    column_count    INTEGER,
    duration_ms     INTEGER,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_scans_tenant     ON dq.t_dq_scans(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_scans_connection ON dq.t_dq_scans(connection_id);
CREATE INDEX IF NOT EXISTS idx_dq_scans_target     ON dq.t_dq_scans(connection_id, schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_dq_scans_status     ON dq.t_dq_scans(status);
CREATE INDEX IF NOT EXISTS idx_dq_scans_created    ON dq.t_dq_scans(created_at DESC);

-- ---------------------------------------------------------------------------
-- dq.t_dq_column_profiles — per-column statistics for a single scan.
--
-- BRD Table 19 fields: null_rate, distinct_count, min/max, mean/median/stddev,
-- top10_values, length stats, sample values, inferred semantic type, row count.
--
-- raw_metrics JSONB carries forward-compatible extras (e.g. percentiles, top-K
-- with counts) without requiring schema migrations as Phase 2 metrics evolve.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_column_profiles (
    id                       SERIAL PRIMARY KEY,
    scan_id                  INTEGER NOT NULL REFERENCES dq.t_dq_scans(id) ON DELETE CASCADE,
    tenant_id                INTEGER NOT NULL REFERENCES public.t_tenants(id),
    connection_id            UUID    NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name              VARCHAR(255) NOT NULL,
    table_name               VARCHAR(255) NOT NULL,
    column_name              VARCHAR(255) NOT NULL,
    ordinal_position         INTEGER,
    declared_data_type       VARCHAR(100),       -- e.g. 'INTEGER', 'VARCHAR(255)'
    type_category            VARCHAR(20)         -- numeric|string|datetime|boolean|other
                             CHECK (type_category IN
                                    ('numeric','string','datetime','boolean','other')),

    -- Counts
    row_count                BIGINT,
    non_null_count           BIGINT,
    null_count               BIGINT,
    null_rate                NUMERIC(6, 5),       -- 0.00000 .. 1.00000
    pseudo_null_count        BIGINT,              -- '', 'null', 'N/A', '-', etc.
    pseudo_null_rate         NUMERIC(6, 5),
    distinct_count           BIGINT,
    distinct_rate            NUMERIC(6, 5),

    -- Numeric / datetime
    min_value                TEXT,                -- stringified to be type-agnostic
    max_value                TEXT,
    mean_value               DOUBLE PRECISION,
    stddev_value             DOUBLE PRECISION,
    median_value             DOUBLE PRECISION,

    -- String length
    min_length               INTEGER,
    max_length               INTEGER,
    avg_length               DOUBLE PRECISION,

    -- Distribution / samples
    top_values               JSONB,               -- [{"value":..., "count":...}, ...]
    sample_values            JSONB,               -- ["v1","v2",...]

    -- Inferred semantic type from statistics (BRD FR-PROF: semantic-type inference).
    -- Distinct from t_dq_table_types semantic type (which is at table level).
    inferred_column_type     VARCHAR(40),         -- identifier|categorical|free_text|datetime|numeric_continuous|numeric_discrete|boolean|constant|general

    raw_metrics              JSONB,
    profiled_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (scan_id, column_name)
);

CREATE INDEX IF NOT EXISTS idx_dq_col_profiles_scan        ON dq.t_dq_column_profiles(scan_id);
CREATE INDEX IF NOT EXISTS idx_dq_col_profiles_tenant      ON dq.t_dq_column_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_col_profiles_target      ON dq.t_dq_column_profiles(connection_id, schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_dq_col_profiles_inferred    ON dq.t_dq_column_profiles(inferred_column_type);
