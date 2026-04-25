#!/usr/bin/env bash
# Inserts the three Acme departments (Finance, Human Resources, IT) into
# t_groups if they don't already exist, then re-assigns t_users.group_id
# for the seeded users so the "Raise New Request" wizard can populate the
# Receiver department dropdown.
#
# Idempotent: safe to run multiple times.
#
# Usage from your Mac:
#   bash scripts/create_departments.sh

set -uo pipefail

PG_USER="${PG_USER:-dsplatform}"
PG_DB="${PG_DB:-datasharing_dev}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

if [ -z "${PG_CONTAINER:-}" ]; then
  PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres' | head -n1 || true)
fi
[ -z "$PG_CONTAINER" ] && { red "No Postgres container running."; exit 1; }
green "Postgres: $PG_CONTAINER"

psql_q()    { docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc "$1" 2>/dev/null; }
psql_run()  { docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c   "$1" 2>&1; }

blue "[1/4] Resolving tenant id …"
TENANT_ID=$(psql_q "SELECT id FROM t_tenants WHERE slug='acme' LIMIT 1;")
if [ -z "$TENANT_ID" ]; then
  yellow "  ! No tenant with slug='acme'. Creating one …"
  psql_run "INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
            VALUES ('Acme Corporation', 'شركة أكمي', 'acme', 'internal_org',
                    'Nora Al-Rashid', 'nora.dpo@acme.local')
            ON CONFLICT (slug) DO NOTHING;" >/dev/null
  TENANT_ID=$(psql_q "SELECT id FROM t_tenants WHERE slug='acme' LIMIT 1;")
fi
green "  ✓ tenant_id=$TENANT_ID"

blue "[2/4] Inserting departments into t_groups …"
DEPARTMENTS=(
  "Finance|المالية|finance|Finance and accounting"
  "Human Resources|الموارد البشرية|hr|People operations"
  "IT|تقنية المعلومات|it|Information technology"
)
for dep in "${DEPARTMENTS[@]}"; do
  IFS='|' read -r NAME NAME_AR SLUG DESC <<< "$dep"
  psql_run "INSERT INTO t_groups (tenant_id, name, name_ar, slug, description, is_active)
            VALUES ($TENANT_ID, '$NAME', '$NAME_AR', '$SLUG', '$DESC', true)
            ON CONFLICT (tenant_id, slug) DO UPDATE SET is_active = true;" >/dev/null
  GID=$(psql_q "SELECT id FROM t_groups WHERE tenant_id=$TENANT_ID AND slug='$SLUG';")
  green "  ✓ $NAME → id=$GID"
done

blue "[3/4] Assigning t_users.group_id by email suffix …"
declare -a USER_DEPT=(
  "ahmed.do@acme.local|finance"
  "sara.fin@acme.local|finance"
  "omar.fin@acme.local|finance"
  "fatima.do@acme.local|hr"
  "khalid.hr@acme.local|hr"
  "maha.hr@acme.local|hr"
  "youssef.do@acme.local|it"
  "layla.it@acme.local|it"
  "faisal.it@acme.local|it"
)
for ud in "${USER_DEPT[@]}"; do
  IFS='|' read -r EMAIL DEPT <<< "$ud"
  GID=$(psql_q "SELECT id FROM t_groups WHERE tenant_id=$TENANT_ID AND slug='$DEPT';")
  if [ -z "$GID" ]; then
    yellow "  ! $EMAIL — no group with slug=$DEPT, skipping"
    continue
  fi
  EXISTS=$(psql_q "SELECT 1 FROM t_users WHERE email='$EMAIL' LIMIT 1;")
  if [ -z "$EXISTS" ]; then
    yellow "  ! $EMAIL — no row in t_users, skipping"
    continue
  fi
  psql_run "UPDATE t_users SET group_id=$GID WHERE email='$EMAIL';" >/dev/null
  green "  ✓ $EMAIL → group_id=$GID ($DEPT)"
done

blue "[4/4] Final state:"
echo
echo "  --- t_groups ---"
psql_q "SELECT id, name, slug, is_active FROM t_groups WHERE tenant_id=$TENANT_ID ORDER BY id;" \
  | sed 's/^/    /' || true
echo
echo "  --- t_users.group_id ---"
psql_q "SELECT email, group_id FROM t_users WHERE tenant_id=$TENANT_ID ORDER BY email;" \
  | sed 's/^/    /' || true

echo
green "Done. Refresh /data-sharing/new in the browser (Cmd+Shift+R) and the"
green "Receiver department dropdown should now list Finance, Human Resources, IT."
