-- 018_dq_profile_fks.sql
-- IDQP — Phase 1.5: link existing scans / active rules / issues to a profile.
--
-- Strategy: add nullable profile_id columns (additive — no data loss), then
-- backfill by creating one profile per distinct (tenant, conn, schema, table)
-- found anywhere in the three child tables and pointing the children at it.
--
-- profile_id is left NULLABLE for now. A follow-up migration will tighten
-- it to NOT NULL once the application code is updated to always set it on
-- INSERT (Step 3.5.b service refactor). Doing both at once would break any
-- in-flight INSERTs from the running API.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS, ON CONFLICT DO NOTHING on the
-- backfill insert, NULL-only updates on the FK refresh.

-- ---------------------------------------------------------------------------
-- 1. Add the nullable FK columns.
-- ---------------------------------------------------------------------------
ALTER TABLE dq.t_dq_scans
    ADD COLUMN IF NOT EXISTS profile_id INTEGER
        REFERENCES dq.t_dq_profiles(id) ON DELETE CASCADE;

ALTER TABLE dq.t_dq_active_rules
    ADD COLUMN IF NOT EXISTS profile_id INTEGER
        REFERENCES dq.t_dq_profiles(id) ON DELETE CASCADE;

ALTER TABLE dq.t_dq_issues
    ADD COLUMN IF NOT EXISTS profile_id INTEGER
        REFERENCES dq.t_dq_profiles(id) ON DELETE CASCADE;

-- ---------------------------------------------------------------------------
-- 2. Backfill: one profile per distinct (tenant, conn, schema, table).
--
-- Default name = "{schema}.{table}". If the user already created a profile
-- with that name (unlikely on a first run but possible), ON CONFLICT just
-- skips — the existing profile wins and gets the orphaned children attached.
-- ---------------------------------------------------------------------------
INSERT INTO dq.t_dq_profiles (
    tenant_id, name, description, location_path,
    connection_id, schema_name, table_name,
    sampling_mode, drill_down, ai_enabled
)
SELECT DISTINCT
    sub.tenant_id,
    sub.schema_name || '.' || sub.table_name AS name,
    'Auto-created during Phase 1.5 backfill from existing scan history.' AS description,
    'Default' AS location_path,
    sub.connection_id, sub.schema_name, sub.table_name,
    'all', TRUE, TRUE
FROM (
    SELECT tenant_id, connection_id, schema_name, table_name FROM dq.t_dq_scans
    UNION
    SELECT tenant_id, connection_id, schema_name, table_name FROM dq.t_dq_active_rules
    UNION
    SELECT tenant_id, connection_id, schema_name, table_name FROM dq.t_dq_issues
) sub
ON CONFLICT (tenant_id, name) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. Wire each child table's rows to its profile. NULL-guarded so a re-run
-- of this migration is a no-op for already-linked rows.
-- ---------------------------------------------------------------------------
UPDATE dq.t_dq_scans s
   SET profile_id = p.id
  FROM dq.t_dq_profiles p
 WHERE s.profile_id IS NULL
   AND s.tenant_id     = p.tenant_id
   AND s.connection_id = p.connection_id
   AND s.schema_name   = p.schema_name
   AND s.table_name    = p.table_name;

UPDATE dq.t_dq_active_rules ar
   SET profile_id = p.id
  FROM dq.t_dq_profiles p
 WHERE ar.profile_id IS NULL
   AND ar.tenant_id     = p.tenant_id
   AND ar.connection_id = p.connection_id
   AND ar.schema_name   = p.schema_name
   AND ar.table_name    = p.table_name;

UPDATE dq.t_dq_issues i
   SET profile_id = p.id
  FROM dq.t_dq_profiles p
 WHERE i.profile_id IS NULL
   AND i.tenant_id     = p.tenant_id
   AND i.connection_id = p.connection_id
   AND i.schema_name   = p.schema_name
   AND i.table_name    = p.table_name;

-- ---------------------------------------------------------------------------
-- 4. Indexes.
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_dq_scans_profile        ON dq.t_dq_scans(profile_id);
CREATE INDEX IF NOT EXISTS idx_dq_active_rules_profile ON dq.t_dq_active_rules(profile_id);
CREATE INDEX IF NOT EXISTS idx_dq_issues_profile       ON dq.t_dq_issues(profile_id);
