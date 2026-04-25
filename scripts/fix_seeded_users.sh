#!/usr/bin/env bash
# Restores the 11 seeded Datarix users to a working state.
#
# Two things this fixes:
#
# 1. Keycloak — email/firstName/lastName get wiped during the seed's second
#    PUT (kc_set_attributes), and Keycloak 24's User Profile validation
#    treats missing email as "Account is not fully set up", so direct-grant
#    login returns invalid_grant.
#    Fix: kcadm update on each user with the correct profile fields.
#
# 2. Postgres — the seed assigns t_users.group_id ONLY when the seed runs
#    end-to-end. If it errored mid-way (e.g. Keycloak unavailable), users
#    end up with group_id=NULL and the "you can't request from your own
#    department" guard breaks.
#    Fix: derive the department from the email suffix and UPDATE.
#
# Runs everything via docker exec (no python3 dependency on the host).
#
# Usage from your Mac:
#   bash scripts/fix_seeded_users.sh

set -uo pipefail

REALM="${REALM:-datasharing-dev}"
KC_ADMIN_USER="${KC_ADMIN_USER:-admin}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-admin}"
PG_USER="${PG_USER:-dsplatform}"
PG_DB="${PG_DB:-datasharing_dev}"
DEFAULT_PASSWORD="${DEFAULT_PASSWORD:-Test123!}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

# Auto-detect containers.
if [ -z "${KC_CONTAINER:-}" ]; then
  KC_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'keycloak' | head -n1 || true)
fi
if [ -z "${PG_CONTAINER:-}" ]; then
  PG_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'postgres' | head -n1 || true)
fi
[ -z "$KC_CONTAINER" ] && { red "No Keycloak container running."; exit 1; }
[ -z "$PG_CONTAINER" ] && { red "No Postgres container running."; exit 1; }
green "Keycloak: $KC_CONTAINER"
green "Postgres: $PG_CONTAINER"

KCADM=/opt/keycloak/bin/kcadm.sh

blue "[1/3] Authenticating kcadm …"
docker exec "$KC_CONTAINER" "$KCADM" config credentials \
  --server http://localhost:8080 --realm master \
  --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASS" >/dev/null
green "  ✓ admin logged in"

# ── User table ───────────────────────────────────────────────────
# (email | firstName | lastName | dept_slug — empty for non-dept users)
read -r -d '' USERS <<'EOF' || true
superadmin@datasharing.local|Super|Admin|
nora.dpo@acme.local|Nora|Al-Rashid|
ahmed.do@acme.local|Ahmed|Al-Farsi|finance
sara.fin@acme.local|Sara|Al-Harbi|finance
omar.fin@acme.local|Omar|Al-Otaibi|finance
fatima.do@acme.local|Fatima|Al-Qahtani|hr
khalid.hr@acme.local|Khalid|Al-Dosari|hr
maha.hr@acme.local|Maha|Al-Shehri|hr
youssef.do@acme.local|Youssef|Al-Zahrani|it
layla.it@acme.local|Layla|Al-Ghamdi|it
faisal.it@acme.local|Faisal|Al-Mutairi|it
EOF

psql_q() {
  docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc "$1" 2>/dev/null
}

# Get a user's Keycloak id by username (returns plain id, no JSON).
kc_user_id() {
  local email="$1"
  docker exec "$KC_CONTAINER" "$KCADM" get users \
    -r "$REALM" -q "username=$email" -q "exact=true" --fields id 2>/dev/null \
    | grep -E '"id"' | head -n1 | sed -E 's/.*"id" *: *"([^"]+)".*/\1/'
}

blue "[2/3] Patching Keycloak profile fields + clearing requiredActions …"
echo "$USERS" | while IFS='|' read -r EMAIL FIRST LAST DEPT; do
  [ -z "$EMAIL" ] && continue
  KC_ID=$(kc_user_id "$EMAIL")
  if [ -z "$KC_ID" ]; then
    yellow "  • $EMAIL — not in Keycloak, skipping"
    continue
  fi
  docker exec "$KC_CONTAINER" "$KCADM" update "users/$KC_ID" \
    -r "$REALM" \
    -s "email=$EMAIL" \
    -s "firstName=$FIRST" \
    -s "lastName=$LAST" \
    -s 'emailVerified=true' \
    -s 'enabled=true' \
    -s 'requiredActions=[]' >/dev/null 2>&1

  docker exec "$KC_CONTAINER" "$KCADM" set-password \
    -r "$REALM" --userid "$KC_ID" \
    --new-password "$DEFAULT_PASSWORD" --temporary=false >/dev/null 2>&1
  green "  ✓ $EMAIL  ($FIRST $LAST)"
done

blue "[3/3] Repairing t_users.group_id assignments by email-suffix …"
TENANT_ID=$(psql_q "SELECT id FROM t_tenants WHERE slug='acme' LIMIT 1;")
if [ -z "$TENANT_ID" ]; then
  yellow "  ! No tenant with slug='acme' — skipping group assignments."
else
  echo "$USERS" | while IFS='|' read -r EMAIL FIRST LAST DEPT; do
    [ -z "$EMAIL" ] && continue
    [ -z "$DEPT" ] && continue
    GRP_ID=$(psql_q "SELECT id FROM t_groups WHERE tenant_id=$TENANT_ID AND slug='$DEPT' LIMIT 1;")
    if [ -z "$GRP_ID" ]; then
      yellow "  ! $EMAIL — no group with slug='$DEPT' in tenant $TENANT_ID, skipping"
      continue
    fi
    psql_q "UPDATE t_users SET group_id=$GRP_ID WHERE email='$EMAIL';" >/dev/null
    green "  ✓ $EMAIL → group_id=$GRP_ID ($DEPT)"
  done
fi

echo
blue "Verifying with sara.fin@acme.local …"
RESP=$(curl -s -o /tmp/datarix-login.json -w "%{http_code}" -X POST \
  "http://localhost:8000/api/v1/platform/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"sara.fin@acme.local","password":"Test123!"}')
if [ "$RESP" = "200" ]; then
  GID=$(grep -oE '"group_id":[^,}]*' /tmp/datarix-login.json | head -n1)
  green "  ✓ login → 200, $GID"
else
  red   "  ✗ login → $RESP"
  cat /tmp/datarix-login.json; echo
fi
rm -f /tmp/datarix-login.json

green ""
green "Done. All seeded users should now log in with password '$DEFAULT_PASSWORD'."
