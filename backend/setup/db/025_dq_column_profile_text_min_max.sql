-- 025_dq_column_profile_text_min_max.sql
-- IDQP — Phase 1: extend min/max persistence to non-numeric columns.
--
-- Migration 023 re-introduced min_value / max_value as NUMERIC(38,10),
-- which only fits numeric columns. Date and string columns therefore
-- showed "—" in the Min · Max tile even though MIN(col) / MAX(col) on
-- those types is just as analytically valuable (date range = freshness;
-- alphabetical bounds = sort-order sanity check).
--
-- This migration adds parallel TEXT columns. The numeric columns stay
-- as-is so percentile math doesn't change; the new text columns are
-- written by the profiler for `string` and `datetime` categories.
--
-- POLICY NOTE — same single-row leak class as 023
-- ================================================
-- min_text / max_text each store one specific row's value (the
-- alphabetically/chronologically smallest or largest). This is the same
-- leak shape that migration 023 explicitly accepted for numerics. For
-- tenants with PII-bearing string columns (names, emails) the operator
-- should either (a) exclude those columns from profiling, or (b) revisit
-- this decision before onboarding.
--
-- Top values continue to be live-only (never persisted), unchanged by
-- this migration.
--
-- Idempotent.

ALTER TABLE dq.t_dq_column_profiles
    ADD COLUMN IF NOT EXISTS min_text TEXT,
    ADD COLUMN IF NOT EXISTS max_text TEXT;

COMMENT ON COLUMN dq.t_dq_column_profiles.min_text IS
    'Smallest non-null value for string/datetime columns (ISO format for dates). Single-row leak class — see migration 025 header.';
COMMENT ON COLUMN dq.t_dq_column_profiles.max_text IS
    'Largest non-null value for string/datetime columns (ISO format for dates). Single-row leak class — see migration 025 header.';
