-- 017_dq_profiles.sql
-- IDQP — Phase 1.5: Profile Assets.
--
-- A *Profile* is the unit of work for DQ — named, saveable, ownable, and
-- locatable inside a folder hierarchy (e.g. DQ_DWH/HEALTH_OPD). It bundles
-- the source binding (connection + schema + table), profiling configuration
-- (sampling, drill-down, AI on/off), and inherits ownership of every scan,
-- active rule, issue, and score-history row that targets the same source.
--
-- This migration creates the table only. The next migration (018) wires up
-- profile_id FKs on scans/active_rules/issues and backfills them from the
-- existing rows so we don't lose any history.
--
-- Idempotent (CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS dq.t_dq_profiles (
    id SERIAL PRIMARY KEY,
    tenant_id     INTEGER NOT NULL REFERENCES public.t_tenants(id) ON DELETE CASCADE,

    -- User-facing name. Unique within a tenant. Allows multiple profiles
    -- for the same (conn, schema, table) when the user wants variants
    -- (e.g. one with strict thresholds, one with lenient).
    name          VARCHAR(255) NOT NULL,
    description   TEXT,

    -- Optional folder-style path for grouping in the UI.
    -- Example: 'DQ_DWH/HEALTH_OPD'. NULL/empty = top-level.
    location_path VARCHAR(500),

    -- Source binding.
    connection_id UUID NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name   VARCHAR(255) NOT NULL,
    table_name    VARCHAR(255) NOT NULL,

    -- Profiling configuration.
    --   'all'     = scan every row (default; matches today's behaviour)
    --   'first_n' = LIMIT sample_size in the SQL (cheap, biased)
    --   'random'  = TABLESAMPLE / ORDER BY random() LIMIT N (more expensive)
    sampling_mode VARCHAR(20) NOT NULL DEFAULT 'all'
                  CHECK (sampling_mode IN ('all', 'first_n', 'random')),
    sample_size   INTEGER,
    drill_down    BOOLEAN NOT NULL DEFAULT TRUE,
    ai_enabled    BOOLEAN NOT NULL DEFAULT TRUE,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by    INTEGER REFERENCES public.t_users(id),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Sanity: if first_n / random, sample_size must be set.
    CONSTRAINT chk_sample_size_when_sampling
        CHECK (sampling_mode = 'all' OR (sample_size IS NOT NULL AND sample_size > 0)),

    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_dq_profiles_tenant   ON dq.t_dq_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_profiles_target   ON dq.t_dq_profiles(connection_id, schema_name, table_name);
CREATE INDEX IF NOT EXISTS idx_dq_profiles_location ON dq.t_dq_profiles(location_path);

-- ---------------------------------------------------------------------------
-- History — every profile change is auditable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_profiles_hist (
    hist_id SERIAL PRIMARY KEY,
    id            INTEGER NOT NULL,
    tenant_id     INTEGER,
    name          VARCHAR(255),
    description   TEXT,
    location_path VARCHAR(500),
    connection_id UUID,
    schema_name   VARCHAR(255),
    table_name    VARCHAR(255),
    sampling_mode VARCHAR(20),
    sample_size   INTEGER,
    drill_down    BOOLEAN,
    ai_enabled    BOOLEAN,
    created_at    TIMESTAMPTZ,
    created_by    INTEGER,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by    VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_profiles_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_profiles_hist (
        id, tenant_id, name, description, location_path,
        connection_id, schema_name, table_name,
        sampling_mode, sample_size, drill_down, ai_enabled,
        created_at, created_by, changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.name, OLD.description, OLD.location_path,
        OLD.connection_id, OLD.schema_name, OLD.table_name,
        OLD.sampling_mode, OLD.sample_size, OLD.drill_down, OLD.ai_enabled,
        OLD.created_at, OLD.created_by, current_user
    );
    -- COALESCE so BEFORE-DELETE doesn't get cancelled by NEW=NULL.
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_profiles_hist ON dq.t_dq_profiles;
CREATE TRIGGER trg_dq_profiles_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_profiles
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_profiles_hist();
