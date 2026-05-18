-- 026_dq_profile_selected_columns.sql
-- IDQP — Phase 1: per-profile column-subset selection.
--
-- Today the profiler scans every column returned by information_schema.
-- For wide tables (200+ columns) that's wasteful; users want to focus the
-- profile on a meaningful subset (the Informatica-style "Selected 163 of
-- 224" picker — see screen 2 of the Informatica reference workflow).
--
-- This migration adds a TEXT[] column to t_dq_profiles holding the names
-- of the columns to profile. Semantics:
--   - NULL  → profile every column the source DB advertises (current
--             behaviour; existing rows keep working unchanged).
--   - []    → profile *no* columns (degenerate; the profiler short-circuits
--             with an explicit "no columns selected" error rather than
--             silently producing zero column profiles).
--   - non-empty → profile exactly these columns; drop everything else.
--
-- The profiler intersects the live information_schema column list with
-- this set, so a column that disappears from the source is silently
-- skipped (not an error).
--
-- Idempotent.

ALTER TABLE dq.t_dq_profiles
    ADD COLUMN IF NOT EXISTS selected_columns TEXT[];

COMMENT ON COLUMN dq.t_dq_profiles.selected_columns IS
    'NULL = profile all columns. Non-NULL array = profile only these column names (intersected with the live information_schema list).';
