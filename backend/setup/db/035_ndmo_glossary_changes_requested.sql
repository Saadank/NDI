-- 035_ndmo_glossary_changes_requested.sql
-- Adds the distinct `changes_requested` term status.
--
-- When a Data Owner requests changes on a submitted (new) term, the term must
-- be visibly "Changes Requested" — NOT collapsed back to a plain Draft — so
-- the steward sees the owner's note and can edit & resubmit (BRD WF-02 4b /
-- design E6).  This widens the status CHECK on an already-deployed DB; fresh
-- installs get the wider constraint directly from 034.
--
-- Idempotent: drops + re-adds the CHECK constraint to the current value.

DO $$
BEGIN
    -- Drop the existing status CHECK (name is deterministic for an inline
    -- column CHECK: <table>_<column>_check).
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 't_glossary_terms_status_check'
    ) THEN
        ALTER TABLE ndmo.t_glossary_terms
            DROP CONSTRAINT t_glossary_terms_status_check;
    END IF;

    -- Widen the column so 'changes_requested' fits, then re-add the CHECK.
    ALTER TABLE ndmo.t_glossary_terms
        ALTER COLUMN status TYPE VARCHAR(20);

    ALTER TABLE ndmo.t_glossary_terms
        ADD CONSTRAINT t_glossary_terms_status_check
        CHECK (status IN ('draft', 'under_review', 'approved',
                          'deprecated', 'changes_requested'));
END$$;
