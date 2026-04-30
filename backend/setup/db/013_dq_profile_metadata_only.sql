-- 013_dq_profile_metadata_only.sql
-- Privacy hardening: dq.t_dq_column_profiles must hold ONLY metadata about
-- the source data, never raw row values. Anything that's a single row's
-- actual value (min/max, sampled rows, top-10 values) is dropped here.
--
-- Replaced by non-leaking summaries:
--   - dominant_pattern              e.g. "Aaa-999" or "EMAIL"
--   - pattern_conformance_rate      what % of sampled values match the dominant pattern
--   - top_patterns                  top-N pattern signatures with counts (no values)
--
-- Aggregates (mean, stddev, median, length stats) are kept — they describe
-- the distribution rather than expose individual records. Min/max values are
-- *not* kept; users can fetch them live via the source connector when needed.
--
-- Idempotent (DROP/ADD COLUMN IF EXISTS / IF NOT EXISTS).

ALTER TABLE dq.t_dq_column_profiles DROP COLUMN IF EXISTS min_value;
ALTER TABLE dq.t_dq_column_profiles DROP COLUMN IF EXISTS max_value;
ALTER TABLE dq.t_dq_column_profiles DROP COLUMN IF EXISTS top_values;
ALTER TABLE dq.t_dq_column_profiles DROP COLUMN IF EXISTS sample_values;

ALTER TABLE dq.t_dq_column_profiles
    ADD COLUMN IF NOT EXISTS dominant_pattern         VARCHAR(120),
    ADD COLUMN IF NOT EXISTS pattern_conformance_rate NUMERIC(6,5),
    ADD COLUMN IF NOT EXISTS top_patterns             JSONB;

CREATE INDEX IF NOT EXISTS idx_dq_col_profiles_dominant_pattern
    ON dq.t_dq_column_profiles(dominant_pattern);
