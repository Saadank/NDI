-- dev_clear_dq_scans.sql
-- Dev-only helper: wipe DQ scan history while keeping the configuration
-- you spent time on (profiles, dictionary, active rules, semantic types).
--
-- NOT a migration — kept outside backend/setup/db/ so docker-entrypoint
-- never replays it on container rebuild. Run manually:
--
--   docker exec -i datasharing-1st-postgres-1 \
--       psql -U dsplatform -d datasharing_dev < docs/dev_clear_dq_scans.sql

DELETE FROM dq.t_dq_issues;
DELETE FROM dq.t_dq_column_profiles;
DELETE FROM dq.t_dq_scans;

ALTER SEQUENCE dq.t_dq_issues_id_seq          RESTART WITH 1;
ALTER SEQUENCE dq.t_dq_column_profiles_id_seq RESTART WITH 1;
ALTER SEQUENCE dq.t_dq_scans_id_seq           RESTART WITH 1;

-- Verify
SELECT 'scans' AS tbl, COUNT(*) FROM dq.t_dq_scans
UNION ALL SELECT 'column_profiles', COUNT(*) FROM dq.t_dq_column_profiles
UNION ALL SELECT 'issues',          COUNT(*) FROM dq.t_dq_issues;
