-- 011_dq_core.sql
-- Intelligent Data Quality Platform (IDQP) — Phase 1, Step 1
-- Foundation tables: table semantic typing (BRD §4.2, FR-TYPE).
--
-- Schema isolation: all DQ objects live in the dedicated `dq` schema so the
-- product can be dropped/backed-up/permissioned as a single unit. Cross-schema
-- foreign keys to public.t_tenants / public.t_users / public.t_connections are
-- intentional — DQ depends on platform identity, not the other way around.
--
-- This file is idempotent. Re-running it on an already-initialised DB will:
--   1. create the dq schema if missing
--   2. move pre-existing DQ tables/functions out of `public` into `dq`
--      (safe ALTER ... SET SCHEMA — preserves all data)
--   3. create remaining tables/functions only if they don't already exist
--
-- Reuses existing data-sharing assets:
--   - public.t_connections, public.t_schemas (BRD FR-CON-01..06 connectivity)
--   - public.t_tenants, public.t_users, public.t_tenant_products (platform core)

-- ---------------------------------------------------------------------------
-- Schema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS dq;

-- Self-heal: move objects an earlier version of this migration may have
-- created in `public` into `dq`. No-op on fresh installs.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 't_dq_table_types') THEN
        EXECUTE 'ALTER TABLE public.t_dq_table_types SET SCHEMA dq';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = 't_dq_table_types_hist') THEN
        EXECUTE 'ALTER TABLE public.t_dq_table_types_hist SET SCHEMA dq';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_proc p
               JOIN pg_namespace n ON p.pronamespace = n.oid
               WHERE n.nspname = 'public' AND p.proname = 'fn_dq_table_types_hist') THEN
        EXECUTE 'ALTER FUNCTION public.fn_dq_table_types_hist() SET SCHEMA dq';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- dq.t_dq_table_types — DQ team's semantic-type assignment for source tables.
--
-- BRD §4.2: "Table semantic types govern how rules are applied. A claims table
-- should not be penalized for having duplicate customer IDs — that is expected
-- behavior. Semantic typing solves this by making rule application context-aware."
--
-- One row per (connection, schema, table). Untyped tables flow through the
-- conservative default at validation time and earn a "low context confidence"
-- badge in the UI (FR-TYPE-02).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dq.t_dq_table_types (
    id SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES public.t_tenants(id),
    connection_id  UUID    NOT NULL REFERENCES public.t_connections(id) ON DELETE CASCADE,
    schema_name    VARCHAR(255) NOT NULL,
    table_name     VARCHAR(255) NOT NULL,
    semantic_type  VARCHAR(50)  NOT NULL
                   CHECK (semantic_type IN
                          ('master_data','transaction','event_log',
                           'reference','staging','snapshot')),
    note           TEXT,
    assigned_by    INTEGER NOT NULL REFERENCES public.t_users(id),
    assigned_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (connection_id, schema_name, table_name)
);

CREATE INDEX IF NOT EXISTS idx_dq_table_types_tenant      ON dq.t_dq_table_types(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dq_table_types_connection  ON dq.t_dq_table_types(connection_id);
CREATE INDEX IF NOT EXISTS idx_dq_table_types_type        ON dq.t_dq_table_types(semantic_type);

-- History table — every type reassignment is auditable per FR-TYPE policy
-- and the platform-wide "audit-complete" architectural principle (BRD §6.1).
CREATE TABLE IF NOT EXISTS dq.t_dq_table_types_hist (
    hist_id SERIAL PRIMARY KEY,
    id            INTEGER NOT NULL,
    tenant_id     INTEGER,
    connection_id UUID,
    schema_name   VARCHAR(255),
    table_name    VARCHAR(255),
    semantic_type VARCHAR(50),
    note          TEXT,
    assigned_by   INTEGER,
    assigned_at   TIMESTAMPTZ,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by    VARCHAR(255)
);

CREATE OR REPLACE FUNCTION dq.fn_dq_table_types_hist() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO dq.t_dq_table_types_hist (
        id, tenant_id, connection_id, schema_name, table_name,
        semantic_type, note, assigned_by, assigned_at, changed_by
    ) VALUES (
        OLD.id, OLD.tenant_id, OLD.connection_id, OLD.schema_name, OLD.table_name,
        OLD.semantic_type, OLD.note, OLD.assigned_by, OLD.assigned_at, current_user
    );
    -- BEFORE UPDATE OR DELETE: NEW is NULL on DELETE, so returning NEW would
    -- silently abort the delete. COALESCE keeps both paths working.
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dq_table_types_hist ON dq.t_dq_table_types;
CREATE TRIGGER trg_dq_table_types_hist
    BEFORE UPDATE OR DELETE ON dq.t_dq_table_types
    FOR EACH ROW EXECUTE FUNCTION dq.fn_dq_table_types_hist();
