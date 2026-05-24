-- 029_dq_consolidate_uniqueness_concepts.sql
-- IDQP — Collapse three near-duplicate uniqueness concepts into one.
--
-- Phase 1 left us with `primary_identifier_unique`, `business_key_unique`,
-- and `natural_key_unique` as three separate concepts in the dictionary.
-- They all produce `rule_type = unique` and now share identical runtime
-- behaviour (the validator uses the table's entity_key_columns, not the
-- concept, to decide grouping). The three-way split was useful when the
-- concept dictated severity / SQL shape — that's no longer true.
--
-- This migration:
--   1. Creates a single `column_must_be_unique` concept per tenant, with
--      the merged synonym list.
--   2. Dedupes active_rule attachments that would collide post-rewrite
--      (same column with two legacy concepts attached → keep the newest).
--   3. Re-points existing t_dq_active_rules.concept_id from the three
--      old concepts to the new one.
--   4. Disables (NOT deletes) the three old concepts so their history
--      stays queryable and future re-seeds don't recreate them.
--
-- Idempotent — safe to re-run after partial failures (the first version
-- of this file shipped with three bugs and may have left the disable
-- step done but the insert/re-point skipped).

-- ---------------------------------------------------------------------------
-- 1. Insert the consolidated concept for every tenant that has any of the
--    three legacy concepts (enabled OR disabled — a previous botched run
--    may have disabled them already, but we still need to migrate their
--    rule attachments). ON CONFLICT keeps the operation idempotent.
--
--    `applies_to_types` is VARCHAR(50)[] — bare NULL gets inferred as
--    TEXT and the implicit cast rejects, so we type the NULL explicitly.
-- ---------------------------------------------------------------------------
INSERT INTO dq.t_dq_concepts (
    tenant_id, dimension, concept, synonyms,
    rule_type, parameter, severity, applies_to_types,
    notes, enabled, is_seed
)
SELECT DISTINCT
    c.tenant_id,
    'uniqueness',
    'column_must_be_unique',
    ARRAY[
        'id', 'uuid', 'guid', 'key', 'primary_key', 'pk',
        'national_id', 'national_no', 'customer_id', 'client_id',
        'customer_code', 'account_number', 'account_no', 'external_id',
        'person_id', 'subscriber_id',
        'code', 'sku', 'isbn',
        'email', 'username', 'login', 'handle'
    ]::TEXT[],
    'unique',
    '{}'::JSONB,
    'high',
    NULL::VARCHAR(50)[],
    'Column values must be unique. When the table has an entity_key_columns configured, ' ||
    'uniqueness is checked across distinct entity keys (one client repeating the same mobile ' ||
    'across many claims is fine; two clients sharing a mobile is a violation). When no entity ' ||
    'key is set, the column must be globally unique.',
    TRUE,
    TRUE
FROM dq.t_dq_concepts c
WHERE c.dimension = 'uniqueness'
  AND c.concept IN ('primary_identifier_unique','business_key_unique','natural_key_unique')
ON CONFLICT (tenant_id, dimension, concept) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Dedupe rule attachments before the re-point. Active rules have
--    UNIQUE(connection_id, schema_name, table_name, column_name, concept_id);
--    if `mobile` has both primary_identifier_unique AND natural_key_unique
--    attached, both would collapse to the same (..., new_concept_id) and
--    blow the constraint. Keep the row with the largest id (most recent),
--    drop the others.
--
--    The active-rules PK column is `id` (SERIAL PRIMARY KEY in 015) —
--    NOT `active_rule_id` (that's an alias used in some downstream views).
-- ---------------------------------------------------------------------------
DELETE FROM dq.t_dq_active_rules
WHERE id IN (
    SELECT ranked.id FROM (
        SELECT ar.id,
               ROW_NUMBER() OVER (
                   PARTITION BY ar.tenant_id, ar.connection_id,
                                ar.schema_name, ar.table_name, ar.column_name
                   ORDER BY ar.id DESC
               ) AS rn
          FROM dq.t_dq_active_rules ar
          JOIN dq.t_dq_concepts c ON c.id = ar.concept_id
         WHERE c.dimension = 'uniqueness'
           AND c.concept IN ('primary_identifier_unique','business_key_unique','natural_key_unique')
    ) ranked
    WHERE ranked.rn > 1
);

-- ---------------------------------------------------------------------------
-- 3. Re-point remaining active_rules to the new concept. Two-table FROM
--    is fine here — old_c picks out attachments that need rewriting; nc
--    is the destination concept per tenant.
-- ---------------------------------------------------------------------------
UPDATE dq.t_dq_active_rules ar
   SET concept_id = nc.id,
       updated_at = CURRENT_TIMESTAMP
  FROM dq.t_dq_concepts old_c,
       dq.t_dq_concepts nc
 WHERE ar.concept_id  = old_c.id
   AND old_c.dimension = 'uniqueness'
   AND old_c.concept IN ('primary_identifier_unique','business_key_unique','natural_key_unique')
   AND nc.tenant_id  = ar.tenant_id
   AND nc.dimension  = 'uniqueness'
   AND nc.concept    = 'column_must_be_unique';

-- ---------------------------------------------------------------------------
-- 4. Disable the three old concepts. Soft-delete: the rows stay so
--    audit history (t_dq_concepts_hist) and joined queries still resolve,
--    but the matcher's `WHERE enabled = TRUE` skips them and the seed
--    loader's ON CONFLICT DO NOTHING leaves them disabled if it re-runs.
-- ---------------------------------------------------------------------------
UPDATE dq.t_dq_concepts
SET enabled = FALSE
WHERE dimension = 'uniqueness'
  AND concept IN ('primary_identifier_unique','business_key_unique','natural_key_unique')
  AND enabled = TRUE;
