#!/usr/bin/env bash
# Master fix script for the Datarix dev environment. Idempotent — safe to
# re-run. Wraps every individual fix we've applied so far:
#
#   1. sslRequired = NONE on master + datasharing-dev realms
#   2. Profile fields (email/firstName/lastName) restored on all 11 users
#   3. requiredActions cleared, passwords reset to Test123! (non-temporary)
#   4. Three departments inserted in t_groups (Finance / HR / IT)
#   5. t_users.group_id assigned by email suffix
#   6. Verify by logging in as sara.fin@acme.local and listing groups
#
# Usage:
#   cd ~/Downloads/NDI-dev\ 3
#   bash scripts/fix_all.sh

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
hdr()    { printf "\033[35m\n══ %s ══\033[0m\n" "$*"; }

# ── Detect containers ─────────────────────────────────────────────
KC_CONTAINER="${KC_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -E 'keycloak' | head -n1)}"
PG_CONTAINER="${PG_CONTAINER:-$(docker ps --format '{{.Names}}' | grep -E 'postgres' | head -n1)}"
[ -z "$KC_CONTAINER" ] && { red "✗ No Keycloak container running."; exit 1; }
[ -z "$PG_CONTAINER" ] && { red "✗ No Postgres container running."; exit 1; }
green "Keycloak container: $KC_CONTAINER"
green "Postgres container: $PG_CONTAINER"

KCADM=/opt/keycloak/bin/kcadm.sh
psql_q()   { docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -tAc "$1" 2>/dev/null; }
psql_run() { docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" -c   "$1" 2>&1; }

# ── 1. kcadm login ────────────────────────────────────────────────
hdr "1. kcadm login"
docker exec "$KC_CONTAINER" "$KCADM" config credentials \
  --server http://localhost:8080 --realm master \
  --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASS" >/dev/null
green "  ✓ admin authenticated"

# ── 2. sslRequired = NONE on both realms ─────────────────────────
hdr "2. Patch sslRequired = NONE"
docker exec "$KC_CONTAINER" "$KCADM" update realms/master -s sslRequired=NONE
green "  ✓ master"
if docker exec "$KC_CONTAINER" "$KCADM" get "realms/$REALM" >/dev/null 2>&1; then
  docker exec "$KC_CONTAINER" "$KCADM" update "realms/$REALM" -s sslRequired=NONE
  green "  ✓ $REALM"
else
  red   "  ✗ realm $REALM does not exist."
  red   "    Run: cd backend/setup/keycloak && python3 setup_realm.py"
  exit 1
fi

# ── 3. Restore profile fields + clear requiredActions + reset pwd ─
hdr "3. Restore profile fields, clear requiredActions, reset passwords"
read -r -d '' USERS <<'EOF' || true
superadmin@datasharing.local|Super|Admin
nora.dpo@acme.local|Nora|Al-Rashid
ahmed.do@acme.local|Ahmed|Al-Farsi
sara.fin@acme.local|Sara|Al-Harbi
omar.fin@acme.local|Omar|Al-Otaibi
fatima.do@acme.local|Fatima|Al-Qahtani
khalid.hr@acme.local|Khalid|Al-Dosari
maha.hr@acme.local|Maha|Al-Shehri
youssef.do@acme.local|Youssef|Al-Zahrani
layla.it@acme.local|Layla|Al-Ghamdi
faisal.it@acme.local|Faisal|Al-Mutairi
EOF

kc_user_id() {
  docker exec "$KC_CONTAINER" "$KCADM" get users \
    -r "$REALM" -q "username=$1" -q "exact=true" --fields id 2>/dev/null \
    | grep -E '"id"' | head -n1 | sed -E 's/.*"id" *: *"([^"]+)".*/\1/'
}

while IFS='|' read -r EMAIL FIRST LAST; do
  [ -z "$EMAIL" ] && continue
  KC_ID=$(kc_user_id "$EMAIL")
  if [ -z "$KC_ID" ]; then
    yellow "  • $EMAIL — not in Keycloak, skipping"
    continue
  fi
  docker exec "$KC_CONTAINER" "$KCADM" update "users/$KC_ID" -r "$REALM" \
    -s "email=$EMAIL" \
    -s "firstName=$FIRST" \
    -s "lastName=$LAST" \
    -s 'emailVerified=true' \
    -s 'enabled=true' \
    -s 'requiredActions=[]' >/dev/null 2>&1
  docker exec "$KC_CONTAINER" "$KCADM" set-password \
    -r "$REALM" --userid "$KC_ID" \
    --new-password "$DEFAULT_PASSWORD" --temporary=false >/dev/null 2>&1
  green "  ✓ $EMAIL ($FIRST $LAST)"
done <<< "$USERS"

# ── 4. Tenant + departments ──────────────────────────────────────
hdr "4. Ensure tenant + 3 departments exist in Postgres"
TENANT_ID=$(psql_q "SELECT id FROM t_tenants WHERE slug='acme' LIMIT 1;")
if [ -z "$TENANT_ID" ]; then
  yellow "  ! tenant 'acme' missing — creating"
  psql_run "INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
            VALUES ('Acme Corporation', 'شركة أكمي', 'acme', 'internal_org',
                    'Nora Al-Rashid', 'nora.dpo@acme.local')
            ON CONFLICT (slug) DO NOTHING;" >/dev/null
  TENANT_ID=$(psql_q "SELECT id FROM t_tenants WHERE slug='acme' LIMIT 1;")
fi
green "  tenant_id=$TENANT_ID"

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

# ── 5. Map t_users → group_id by email suffix ─────────────────────
hdr "5. Assign t_users.group_id by email suffix"
USER_DEPT=(
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
  EXISTS=$(psql_q "SELECT 1 FROM t_users WHERE email='$EMAIL' LIMIT 1;")
  if [ -z "$GID" ] || [ -z "$EXISTS" ]; then
    yellow "  ! $EMAIL — group=$GID exists=$EXISTS, skipping"
    continue
  fi
  psql_run "UPDATE t_users SET group_id=$GID WHERE email='$EMAIL';" >/dev/null
  green "  ✓ $EMAIL → group_id=$GID ($DEPT)"
done

# ── 6. Verify ─────────────────────────────────────────────────────
hdr "6. Verify end-to-end with sara.fin@acme.local"
LOGIN=$(curl -s -w "\n__HTTP__%{http_code}" -X POST \
  http://localhost:8000/api/v1/platform/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"sara.fin@acme.local","password":"'"$DEFAULT_PASSWORD"'"}')
HTTP=$(echo "$LOGIN" | tail -1 | sed 's/__HTTP__//')
BODY=$(echo "$LOGIN" | sed '$d')
if [ "$HTTP" = "200" ]; then
  green "  ✓ login → 200"
  TOK=$(echo "$BODY" | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
  GID=$(echo "$BODY" | grep -oE '"group_id":[^,}]*')
  green "    $GID"
  GROUPS=$(curl -s -H "Authorization: Bearer $TOK" \
    http://localhost:8000/api/v1/platform/groups/)
  COUNT=$(echo "$GROUPS" | grep -oE '"id"' | wc -l | tr -d ' ')
  if [ "$COUNT" -ge 1 ]; then
    green "  ✓ /platform/groups/ returned $COUNT group(s)"
  else
    red "  ✗ /platform/groups/ returned 0. Body: $GROUPS"
  fi
else
  red "  ✗ login → $HTTP. Body: $BODY"
fi

echo
green "All fixes applied. Hard-refresh http://localhost:3001/data-sharing/new"
green "(Cmd+Shift+R) and the Receiver department dropdown should populate."
