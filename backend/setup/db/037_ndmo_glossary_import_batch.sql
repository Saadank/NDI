-- 037_ndmo_glossary_import_batch.sql
-- Adds t_glossary_terms.import_batch_id so a bulk Excel import (BRD §6.6 /
-- FR-052, design H2) can be rolled back as a whole batch.  Imported terms land
-- as drafts tagged with a shared batch id; "Roll Back Import" deletes the
-- still-draft rows for that batch.  Fresh installs get the column from 034.
-- Idempotent.

ALTER TABLE ndmo.t_glossary_terms
    ADD COLUMN IF NOT EXISTS import_batch_id UUID;

CREATE INDEX IF NOT EXISTS idx_glossary_terms_import_batch
    ON ndmo.t_glossary_terms(tenant_id, import_batch_id)
    WHERE import_batch_id IS NOT NULL;
