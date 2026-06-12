-- 036_ndmo_glossary_candidate_connection_uuid.sql
-- Fix: t_glossary_db_candidates.connection_id was INTEGER, but the platform's
-- connection registry (public.t_connections.id) uses UUID.  The DB-extraction
-- candidate references a connection, so the column must be UUID.
--
-- The table is empty (extraction ships in this slice), so dropping and
-- re-adding the column loses nothing.  Idempotent.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'ndmo'
          AND table_name = 't_glossary_db_candidates'
          AND column_name = 'connection_id'
          AND data_type <> 'uuid'
    ) THEN
        ALTER TABLE ndmo.t_glossary_db_candidates DROP COLUMN connection_id;
        ALTER TABLE ndmo.t_glossary_db_candidates ADD COLUMN connection_id UUID;
    END IF;
END$$;
