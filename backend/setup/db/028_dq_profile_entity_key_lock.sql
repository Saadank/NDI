-- 028_dq_profile_entity_key_lock.sql
-- IDQP — Lock the entity key against scan-time overwrites.
--
-- Phase 1 had a subtle gap: every scan that found a declared PK wrote it
-- to entity_key_columns. So if a user opened the profile, replaced the
-- declared PK with the real business key (e.g. claim_id → national_id),
-- and clicked Run again, the scan silently restored claim_id. Phase 2
-- adds heuristic candidate detection, which would compound the problem —
-- candidates can change between scans as the source data evolves.
--
-- The fix: a per-profile lock that the user implicitly sets by saving
-- their own entity key. While locked, the profiler skips its auto-update
-- step. The user can "Reset to auto-detect" from the UI to unlock and
-- let the next scan re-populate.
--
-- Default false → existing profiles keep auto-updating until a user
-- explicitly saves, which matches their current behaviour exactly.
--
-- Idempotent.

ALTER TABLE dq.t_dq_profiles
    ADD COLUMN IF NOT EXISTS entity_key_locked BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN dq.t_dq_profiles.entity_key_locked IS
    'When TRUE, scans do NOT auto-update entity_key_columns (user has explicitly chosen the value). Set by /entity-key PUT, cleared by Reset to auto-detect.';
