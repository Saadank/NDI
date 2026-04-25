#!/usr/bin/env bash
# Why is the "Receiver department" dropdown empty?
#
# This script hits exactly the endpoint the frontend hits — GET
# /api/v1/platform/groups/ — using a real user's bearer token, and
# also looks straight at the t_groups table in Postgres so we can
# tell whether the issue is:
#   1. The user has no rows in t_groups for their tenant.
#   2. The backend returns groups but they're all is_active=false.
#   3. The endpoint itself is failing (401/403/500).
#
# Usage from your Mac:
#   bash scripts/diagnose_groups.sh sara.fin@acme.local Test123!

set -uo pipefail

API="${API:-http://localhost:8000}"
PG_CONTAINER="${PG_CONTAINER:-datasharing-1st-postgres-1}"
PG_USER="${PG_USER:-dsplatform}"
PG_DB="${PG_DB:-datasharing_dev}"
USER_EMAIL="${1:-sara.fin@acme.local}"
PASS="${2:-Test123!}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

# Auto-detect postgres container if user-provided name doesn't exist.
if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  ALT=$(docker ps --format '{{.Names}}' | grep -E 'postgres' | head -n1 || true)
  if [ -n "$ALT" ]; then PG_CONTAINER="$ALT"; fi
fi

psql_q() { docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc "$1" 2>/dev/null; }

blue "[1/4] Logging in as $USER_EMAIL …"
LOGIN=$(curl -fsS -X POST "$API/api/v1/platform/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(printf '{"username":"%s","password":"%s"}' "$USER_EMAIL" "$PASS")") \
  || { red "Login failed."; exit 1; }
TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")
TENANT_ID=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('user',{}).get('tenant_id'))")
GROUP_ID=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('user',{}).get('group_id'))")
green "  ✓ logged in (tenant_id=$TENANT_ID, my group_id=$GROUP_ID)"

blue "[2/4] Hitting GET /api/v1/platform/groups/ as the user (same call the frontend makes) …"
RESP=$(curl -s -w "\n__HTTP__%{http_code}" -H "Authorization: Bearer $TOKEN" \
  "$API/api/v1/platform/groups/")
HTTP=$(echo "$RESP" | tail -1 | sed 's/__HTTP__//')
BODY=$(echo "$RESP" | sed '$d')

case "$HTTP" in
  200)
    COUNT=$(echo "$BODY" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
    green "  ✓ HTTP 200 — returned $COUNT group(s)"
    if [ "$COUNT" -gt 0 ]; then
      echo "$BODY" | python3 -c '
import json, sys
for g in json.load(sys.stdin):
  print(f"    [{g[\"id\"]:>3}] {g[\"name\"]:<24} active={g[\"is_active\"]} tenant_id={g[\"tenant_id\"]}")
'
      ACTIVE_COUNT=$(echo "$BODY" | python3 -c "import json,sys; print(sum(1 for g in json.load(sys.stdin) if g.get('is_active')))")
      if [ "$ACTIVE_COUNT" = "0" ]; then
        red   "  ✗ All groups are is_active=false — the dropdown filters those out."
        yellow "    Fix: docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c \"UPDATE t_groups SET is_active=true WHERE tenant_id=$TENANT_ID;\""
      fi
    else
      red   "  ✗ Backend returned an empty list — no groups exist for tenant_id=$TENANT_ID."
    fi
    ;;
  401|403)
    red "  ✗ HTTP $HTTP — auth/permission rejected."
    echo "    Body: $BODY"
    ;;
  *)
    red "  ✗ HTTP $HTTP."
    echo "    Body: $BODY"
    ;;
esac

blue "[3/4] Counting rows directly in Postgres …"
if docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  ALL=$(psql_q "SELECT COUNT(*) FROM t_groups WHERE tenant_id = $TENANT_ID;")
  ACT=$(psql_q "SELECT COUNT(*) FROM t_groups WHERE tenant_id = $TENANT_ID AND is_active = true;")
  echo "  t_groups for tenant $TENANT_ID: total=$ALL, active=$ACT"
  if [ "$ALL" = "0" ]; then
    red   "  ✗ No groups in DB for this tenant."
    yellow "    Fix: cd backend/setup/keycloak && python3 seed_test_data.py"
  fi
  echo "  --- listing ---"
  psql_q "SELECT id, name, slug, is_active FROM t_groups WHERE tenant_id = $TENANT_ID ORDER BY id;" | sed 's/^/    /'
else
  yellow "  ! Postgres container '$PG_CONTAINER' not found, skipping DB check."
fi

blue "[4/4] Verdict"
if [ "$HTTP" = "200" ]; then
  COUNT=$(echo "$BODY" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
  if [ "$COUNT" -gt 0 ]; then
    green "  Backend is returning groups. If the dropdown is still empty in the UI:"
    yellow "    - Open DevTools → Network → reload /data-sharing/new and look for the call"
    yellow "      to /api/v1/platform/groups/. Make sure status is 200 and the array is not empty."
    yellow "    - Hard-refresh the page (Cmd+Shift+R) so React Query refetches."
  fi
fi
