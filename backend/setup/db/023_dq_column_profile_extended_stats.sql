-- 023_dq_column_profile_extended_stats.sql
-- IDQP — Phase 1, Step 5.5: extended numeric statistics on column profiles.
--
-- Adds the metrics required by the redesigned per-column scan-results view:
--
--   min_value       — smallest non-null numeric value
--   max_value       — largest non-null numeric value
--   p25_value       — 25th-percentile (lower quartile)
--   p75_value       — 75th-percentile (upper quartile)
--   p95_value       — 95th-percentile (right-tail / outlier boundary)
--
-- median_value already exists (added by 012) but was never populated; the
-- profiler now writes it alongside the new fields.
--
-- ================================================================
-- POLICY NOTE — partial reversal of migration 013
-- ================================================================
-- Migration 013 ("metadata_only") dropped min_value and max_value on the
-- grounds that each is a single row's actual value and therefore leaks one
-- record (e.g. minimum salary reveals one person's salary). It directed
-- callers to fetch min/max live from the source connector instead.
--
-- This migration deliberately re-introduces min_value and max_value as
-- persisted columns. The trade-off was made explicitly: users want the
-- redesigned scan-results tiles to render without a per-column live query.
-- For tenants where min/max would expose PII (payroll, medical, salaries),
-- the operator should either (a) exclude those columns from profiling, or
-- (b) revisit this decision before onboarding such sources.
--
-- The same leak class — "top values" — was NOT re-introduced. Top values
-- continue to be fetched live via /profiles/{id}/columns/{col}/sample-stats
-- and are never persisted.
-- ================================================================
--
-- All numeric fields use NUMERIC(38,10) so they fit BIGINT, DECIMAL, and
-- floating-point ranges without lossy widening at write time. NULL means
-- "not applicable" (column was non-numeric, or had no non-null rows).
--
-- Idempotent (ADD COLUMN IF NOT EXISTS).

ALTER TABLE dq.t_dq_column_profiles
    ADD COLUMN IF NOT EXISTS min_value NUMERIC(38,10),
    ADD COLUMN IF NOT EXISTS max_value NUMERIC(38,10),
    ADD COLUMN IF NOT EXISTS p25_value NUMERIC(38,10),
    ADD COLUMN IF NOT EXISTS p75_value NUMERIC(38,10),
    ADD COLUMN IF NOT EXISTS p95_value NUMERIC(38,10);

COMMENT ON COLUMN dq.t_dq_column_profiles.min_value IS
    'Smallest non-null numeric value. Single-row leak class — see migration 023 header.';
COMMENT ON COLUMN dq.t_dq_column_profiles.max_value IS
    'Largest non-null numeric value. Single-row leak class — see migration 023 header.';
COMMENT ON COLUMN dq.t_dq_column_profiles.p25_value IS
    'Lower-quartile (25th percentile) of non-null numeric values.';
COMMENT ON COLUMN dq.t_dq_column_profiles.p75_value IS
    'Upper-quartile (75th percentile) of non-null numeric values.';
COMMENT ON COLUMN dq.t_dq_column_profiles.p95_value IS
    '95th percentile of non-null numeric values — outlier-boundary signal.';
