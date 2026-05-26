-- 030_dq_dictionary_match.sql
-- IDQP — Validity dimension: dictionary_match rule_type.
--
-- Adds a fifth rule_type to the concepts CHECK constraint so a concept can
-- declare "values in this column must be one of these allowed entries"
-- (e.g. ISO 4217 currency codes, an in-house list of bank names, GCC
-- country codes). The allowed list lives inline on the concept:
--
--   parameter = {
--     "values": ["USD", "EUR", "SAR", ...],
--     "case_sensitive": false   -- optional, default false (trim+lower)
--   }
--
-- Storage choice — JSONB on the concept, not a separate table — is
-- deliberate: it mirrors how format_regex already works (one regex per
-- concept), keeps editing single-modal, and avoids a second migration
-- when we want to ship this. If we later need lists shared across
-- concepts or very large lists, a t_dq_dictionaries table can be added
-- without breaking the rule_type contract — only the parameter shape
-- changes.

-- Find and drop the existing CHECK constraint by introspection — the
-- 014 migration didn't name it explicitly, so we look it up.
DO $$
DECLARE
    constraint_nm TEXT;
BEGIN
    SELECT con.conname INTO constraint_nm
      FROM pg_constraint con
      JOIN pg_class       rel ON rel.oid = con.conrelid
      JOIN pg_namespace   nsp ON nsp.oid = rel.relnamespace
     WHERE nsp.nspname = 'dq'
       AND rel.relname = 't_dq_concepts'
       AND con.contype = 'c'
       AND pg_get_constraintdef(con.oid) ILIKE '%rule_type%';

    IF constraint_nm IS NOT NULL THEN
        EXECUTE format('ALTER TABLE dq.t_dq_concepts DROP CONSTRAINT %I', constraint_nm);
    END IF;
END $$;

ALTER TABLE dq.t_dq_concepts
    ADD CONSTRAINT t_dq_concepts_rule_type_check
    CHECK (rule_type IN
           ('not_null','no_pseudo_nulls',
            'unique','format_regex','dictionary_match'));
