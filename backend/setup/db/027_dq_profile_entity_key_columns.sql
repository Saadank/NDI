-- 027_dq_profile_entity_key_columns.sql
-- IDQP — Uniqueness redesign: per-table entity key.
--
-- The original uniqueness rule grouped rows by the target column alone
-- (`GROUP BY mobile_number HAVING COUNT(*) > 1`), which produces false
-- positives on transactional tables where one business entity legitimately
-- repeats across many rows (e.g. one client with many claims sharing the
-- same mobile). The fix: each table profile carries an "entity key" —
-- the column(s) that identify the underlying business entity for that
-- table — and the uniqueness validator checks
--   COUNT(DISTINCT <entity_key>) > 1
-- so the same mobile appearing under one entity key is fine, but the
-- same mobile appearing under two distinct entity keys is the bug.
--
-- The value can be:
--   NULL or [] → no entity key configured; validator falls back to the
--                legacy `COUNT(*) > 1` check (the column itself must be
--                globally unique, e.g. customers.email on a master-data
--                table).
--   non-empty  → list of column names. Single-column for the common
--                case, multi-column for composite business keys.
--
-- Populated at scan time from declared PK metadata; user can override
-- via the profile UI.
--
-- Idempotent.

ALTER TABLE dq.t_dq_profiles
    ADD COLUMN IF NOT EXISTS entity_key_columns TEXT[];

COMMENT ON COLUMN dq.t_dq_profiles.entity_key_columns IS
    'Column(s) identifying the business entity for uniqueness checks. NULL/empty = legacy COUNT(*) > 1 behaviour; non-empty = COUNT(DISTINCT entity_key) > 1.';
