#!/usr/bin/env bash
# Removes any pending "Required Actions" (Update Password, Verify Email, etc.)
# from every user in the datasharing-dev realm. Keycloak's direct-grant flow
# rejects logins for users who still have requiredActions queued, with the
# cryptic error: invalid_grant / "Account is not fully set up".
#
# Runs entirely via kcadm.sh INSIDE the Keycloak container so it bypasses
# the realm's HTTPS rules.
#
# Usage from your Mac:
#   bash scripts/fix_keycloak_required_actions.sh
#
# To target only one user:
#   bash scripts/fix_keycloak_required_actions.sh sara.fin@acme.local

set -euo pipefail

REALM="${REALM:-datasharing-dev}"
KC_ADMIN_USER="${KC_ADMIN_USER:-admin}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-admin}"
ONLY_USER="${1:-}"
DEFAULT_PASSWORD="${DEFAULT_PASSWORD:-Test123!}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

# Auto-detect the Keycloak container.
if [ -z "${KC_CONTAINER:-}" ]; then
  KC_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'keycloak' | head -n1 || true)
fi
if [ -z "$KC_CONTAINER" ]; then
  red "Could not find a running Keycloak container. Start docker compose first."
  exit 1
fi
green "Using container: $KC_CONTAINER"

KCADM=/opt/keycloak/bin/kcadm.sh
SERVER=http://localhost:8080  # localhost = inside the container

blue "[1/3] Logging into Keycloak via kcadm …"
docker exec "$KC_CONTAINER" "$KCADM" config credentials \
  --server "$SERVER" --realm master \
  --user "$KC_ADMIN_USER" --password "$KC_ADMIN_PASS" >/dev/null
green "  ✓ logged in"

blue "[2/3] Listing users in realm $REALM …"
if [ -n "$ONLY_USER" ]; then
  USERS_JSON=$(docker exec "$KC_CONTAINER" "$KCADM" get users \
    -r "$REALM" -q "username=$ONLY_USER" -q "exact=true" 2>/dev/null)
else
  # Pull up to 200 users; the seeds only create ~10 so this is plenty.
  USERS_JSON=$(docker exec "$KC_CONTAINER" "$KCADM" get users \
    -r "$REALM" -q "max=200" 2>/dev/null)
fi

# Collect (id, username) pairs. We pass them through xargs so we can iterate
# in a portable way without parsing JSON in bash.
COUNT=$(echo "$USERS_JSON" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
green "  ✓ found $COUNT user(s)"
if [ "$COUNT" = "0" ]; then
  red "  No matching users in realm $REALM."
  exit 1
fi

blue "[3/3] Clearing requiredActions + ensuring password is non-temporary …"
# We dump (id<TAB>username<TAB>enabled<TAB>requiredActions) lines via Python,
# then feed them into a bash while-loop. Notes:
#  - Python's f-string can't contain backslashes inside the braces, so we
#    pre-assign keys to local vars and use str.format-style joining.
#  - Bash's $UID is read-only on macOS; use KC_USER_ID instead.
echo "$USERS_JSON" | python3 -c '
import json, sys
for u in json.load(sys.stdin):
  uid = u.get("id", "")
  uname = u.get("username", "")
  enabled = u.get("enabled", True)
  actions = u.get("requiredActions") or []
  print("\t".join([str(uid), str(uname), str(enabled), ",".join(actions)]))
' | while IFS=$'\t' read -r KC_USER_ID UNAME ENABLED ACTIONS; do
  echo "  • $UNAME (enabled=$ENABLED, requiredActions=[$ACTIONS])"
  # Wipe requiredActions and force enabled=true.
  docker exec "$KC_CONTAINER" "$KCADM" update "users/$KC_USER_ID" \
    -r "$REALM" \
    -s 'requiredActions=[]' \
    -s 'enabled=true' \
    -s 'emailVerified=true' >/dev/null

  # Re-set the password as non-temporary so future direct-grant works
  # whether the previous credential was temporary or not.
  docker exec "$KC_CONTAINER" "$KCADM" set-password \
    -r "$REALM" \
    --userid "$KC_USER_ID" \
    --new-password "$DEFAULT_PASSWORD" \
    --temporary=false >/dev/null
  green "    ✓ cleared & password set to '$DEFAULT_PASSWORD'"
done

echo
green "Done. Try logging in again:"
green "  curl -s -X POST http://localhost:8000/api/v1/platform/auth/login \\"
green "       -H 'Content-Type: application/json' \\"
green "       -d '{\"username\":\"sara.fin@acme.local\",\"password\":\"Test123!\"}'"
