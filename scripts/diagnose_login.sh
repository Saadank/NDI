#!/usr/bin/env bash
# Pinpoint exactly why a Datarix user can't log in.
#
# The backend's login flow has FOUR places it can fail:
#   A. Keycloak rejects the credentials (wrong password, wrong realm,
#      direct grants disabled, user disabled in Keycloak).
#   B. Keycloak accepts them but the userinfo endpoint fails.
#   C. Keycloak accepts them but no row exists in t_users with that
#      keycloak_id  →  "User not registered on the platform".
#   D. The DB row exists but is_active=false  →  "User account is disabled".
#
# The frontend hides all four behind "Invalid email or password." This script
# tests each one in order so we know which is breaking.
#
# Usage (run from the project root on your Mac, NOT the sandbox):
#   bash scripts/diagnose_login.sh ahmed.do@acme.local Test123!
#
# Override defaults with env vars if needed:
#   API=http://localhost:8000 KC=http://localhost:8080 \
#   REALM=datasharing-dev CLIENT=datasharing-backend SECRET=dev-client-secret \
#     bash scripts/diagnose_login.sh sara.fin@acme.local Test123!

set -uo pipefail

API="${API:-http://localhost:8000}"
KC="${KC:-http://localhost:8080}"
REALM="${REALM:-datasharing-dev}"
CLIENT="${CLIENT:-datasharing-backend}"
SECRET="${SECRET:-dev-client-secret}"
PG_CONTAINER="${PG_CONTAINER:-datasharing-1st-postgres-1}"
PG_USER="${PG_USER:-dsplatform}"
PG_DB="${PG_DB:-datasharing_dev}"

USER_EMAIL="${1:-ahmed.do@acme.local}"
PASS="${2:-Test123!}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

echo "──────────────────────────────────────────────────────────────"
echo "  Diagnosing login for: $USER_EMAIL"
echo "──────────────────────────────────────────────────────────────"

# ── 0.  Service reachability ──────────────────────────────────────
blue "[0] Checking services …"
for u in "$API/api/docs" "$KC/realms/$REALM"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "$u")
  if [ "$code" = "200" ] || [ "$code" = "303" ]; then
    green "    ✓ $u → $code"
  else
    red   "    ✗ $u → $code"
  fi
done

# ── A.  Keycloak direct grant (raw) ───────────────────────────────
blue "[A] Trying Keycloak direct grant for '$USER_EMAIL' …"
KC_RAW=$(curl -s -m 10 -X POST \
  "$KC/realms/$REALM/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "grant_type=password" \
  --data-urlencode "client_id=$CLIENT" \
  --data-urlencode "client_secret=$SECRET" \
  --data-urlencode "username=$USER_EMAIL" \
  --data-urlencode "password=$PASS")

if echo "$KC_RAW" | grep -q '"access_token"'; then
  green "    ✓ Keycloak accepted credentials."
  KC_OK=1
else
  red   "    ✗ Keycloak rejected credentials."
  echo  "      Response: $KC_RAW"
  KC_OK=0
fi

# ── B.  Backend /auth/login (the real frontend path) ──────────────
blue "[B] Trying backend POST /api/v1/platform/auth/login …"
BE_RESP=$(curl -s -w "\n__HTTP__%{http_code}" -m 10 -X POST \
  "$API/api/v1/platform/auth/login" \
  -H 'Content-Type: application/json' \
  -H "Origin: http://localhost:3001" \
  --data "$(printf '{"username":"%s","password":"%s"}' "$USER_EMAIL" "$PASS")")
BE_CODE=$(echo "$BE_RESP" | tail -1 | sed 's/__HTTP__//')
BE_BODY=$(echo "$BE_RESP" | sed '$d')

if [ "$BE_CODE" = "200" ]; then
  green "    ✓ Backend login succeeded."
else
  red   "    ✗ Backend login failed (HTTP $BE_CODE)."
  echo  "      Body: $BE_BODY"
fi

# ── C.  Postgres: is the user wired up? ───────────────────────────
blue "[C] Checking Postgres for the user row …"
psql_q() {
  docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc "$1" 2>/dev/null
}

if ! docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
  red "    ✗ Postgres container '$PG_CONTAINER' is not running."
  red "      Skipping DB checks. Set PG_CONTAINER=<your-name> if it's named differently."
else
  ROW=$(psql_q "SELECT id, tenant_id, keycloak_id, email, is_active, group_id, platform_role FROM t_users WHERE email = '$USER_EMAIL';")
  if [ -z "$ROW" ]; then
    red   "    ✗ No row in t_users for $USER_EMAIL."
    yellow "      → run: cd backend/setup/keycloak && python3 seed_test_data.py"
  else
    green "    ✓ DB row: $ROW"
  fi

  COUNTS=$(psql_q "SELECT COUNT(*) FROM t_users; SELECT COUNT(*) FROM t_groups; SELECT COUNT(*) FROM t_user_product_roles;" | paste -sd ',' -)
  blue "    table totals (users, groups, product_roles): $COUNTS"
fi

# ── D.  Compare Keycloak ↔ DB ─────────────────────────────────────
blue "[D] Cross-checking Keycloak ↔ DB on this user …"
KC_ADMIN_TOK=$(curl -s -m 10 -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=password&client_id=admin-cli&username=${KC_ADMIN_USER:-admin}&password=${KC_ADMIN_PASS:-admin}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

if [ -z "$KC_ADMIN_TOK" ]; then
  yellow "    ! Could not get Keycloak admin token. Skipping cross-check."
  yellow "      Set KC_ADMIN_USER / KC_ADMIN_PASS env vars if non-default."
else
  KC_USER=$(curl -s -m 10 -H "Authorization: Bearer $KC_ADMIN_TOK" \
    "$KC/admin/realms/$REALM/users?username=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$USER_EMAIL")&exact=true")
  KC_ID=$(echo "$KC_USER" | python3 -c "import json,sys; arr=json.load(sys.stdin); print(arr[0]['id'] if arr else '')")
  KC_ENABLED=$(echo "$KC_USER" | python3 -c "import json,sys; arr=json.load(sys.stdin); print(arr[0].get('enabled') if arr else '')")
  if [ -z "$KC_ID" ]; then
    red   "    ✗ User does not exist in Keycloak realm '$REALM'."
    yellow "      → run: cd backend/setup/keycloak && python3 seed_test_data.py"
  else
    green "    ✓ Keycloak user id: $KC_ID  (enabled=$KC_ENABLED)"
    if docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER"; then
      DB_KCID=$(psql_q "SELECT keycloak_id FROM t_users WHERE email = '$USER_EMAIL';")
      if [ -z "$DB_KCID" ]; then
        red   "    ✗ DB has no row for this email — Keycloak and DB are out of sync."
        yellow "      → run: cd backend/setup/keycloak && python3 seed_test_data.py"
      elif [ "$DB_KCID" != "$KC_ID" ]; then
        red   "    ✗ DB.keycloak_id ($DB_KCID) ≠ Keycloak id ($KC_ID)."
        yellow "      Easiest fix: drop t_users row and re-run seed:"
        yellow "        docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c \"DELETE FROM t_users WHERE email='$USER_EMAIL';\""
        yellow "        cd backend/setup/keycloak && python3 seed_test_data.py"
      else
        green "    ✓ Keycloak id matches t_users.keycloak_id."
      fi
    fi
  fi
fi

# ── Verdict ───────────────────────────────────────────────────────
echo
echo "──────────────────────────────────────────────────────────────"
echo "  VERDICT"
echo "──────────────────────────────────────────────────────────────"
if [ "$BE_CODE" = "200" ]; then
  green "  ✓ Login works end-to-end. The frontend should be able to log in."
  green "    If the UI still says 'Invalid email or password', clear the"
  green "    browser cookies for localhost:3001 and try again — and check"
  green "    NEXT_PUBLIC_API_URL in .env.local matches '$API'."
elif [ "$KC_OK" = "1" ] && [ "$BE_CODE" = "401" ]; then
  red "  ✗ Keycloak accepted the password but the backend rejected the user."
  echo "    Most likely cause: the user exists in Keycloak but NOT in t_users"
  echo "    (the seed script was not run, or only setup_realm.py was run)."
  yellow "    Fix:"
  yellow "      cd backend/setup/keycloak"
  yellow "      python3 seed_test_data.py"
elif [ "$KC_OK" = "0" ]; then
  red "  ✗ Keycloak itself rejected the credentials."
  echo "    Likely causes:"
  echo "      - User does not exist in realm '$REALM' (run seed_test_data.py)."
  echo "      - Wrong password."
  echo "      - Client '$CLIENT' has 'Direct access grants' disabled — open"
  echo "        $KC/admin/master/console/#/$REALM/clients and check the toggle."
  echo "      - Client secret in .env.dev is out of sync with Keycloak."
else
  red "  ✗ Login failed (HTTP $BE_CODE). See body printed above."
fi
