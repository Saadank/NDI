-- 019_dq_profile_id_required.sql
-- IDQP — Phase 1.5 Step 3.5.d follow-up: tighten profile_id from NULLABLE
-- to NOT NULL now that the application code always populates it on insert.
--
-- Migrations 017 + 018 added the column nullable so backfill could populate
-- existing rows without conflicting with the running API. After 3.5.d ships,
-- every new scan / active rule / issue is created with a profile_id, so we
-- can tighten the constraint with confidence.
--
-- Idempotent: ALTER COLUMN ... SET NOT NULL is a no-op if already set.
-- Will fail loudly if any orphan NULL rows remain (correct: a bug to fix
-- before tightening, not silently coerce).

ALTER TABLE dq.t_dq_scans         ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE dq.t_dq_active_rules  ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE dq.t_dq_issues        ALTER COLUMN profile_id SET NOT NULL;
