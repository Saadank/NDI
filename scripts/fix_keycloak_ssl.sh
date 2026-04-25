#!/usr/bin/env bash
# Disables sslRequired on both `master` and `datasharing-dev` realms by
# running kcadm.sh INSIDE the Keycloak container. That bypasses the
# "HTTPS required" wall — kcadm talks to Keycloak over container-local
# loopback (127.0.0.1), which is always considered "internal" regardless
# of the realm's sslRequired setting.
#
# Usage (run from the project root on your Mac):
#   bash scripts/fix_keycloak_ssl.sh
#
# Override defaults if your setup is non-standard:
#   KC_CONTAINER=my-kc KC_ADMIN_USER=admin KC_ADMIN_PASS=admin \
#     bash scripts/fix_keycloak_ssl.sh

set -euo pipefail

KC_ADMIN_USER="${KC_ADMIN_USER:-admin}"
KC_ADMIN_PASS="${KC_ADMIN_PASS:-admin}"
REALM="${REALM:-datasharing-dev}"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

# Auto-detect the Keycloak container if not given.
if [ -z "${KC_CONTAINER:-}" ]; then
  KC_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'keycloak' | head -n1 || true)
fi
if [ -z "$KC_CONTAINER" ]; then
  red "Could not find a running keycloak container."
  red "Set KC_CONTAINER=<name>, e.g.:"
  red "  docker ps --format '{{.Names}}'   # to see your containers"
  exit 1
fi
green "Using container: $KC_CONTAINER"

KCADM=/opt/keycloak/bin/kcadm.sh
SERVER=http://localhost:8080  # ← localhost from kcadm's POV is INSIDE the container

blue "[1/4] Logging into Keycloak via kcadm (inside container) …"
docker exec "$KC_CONTAINER" "$KCADM" config credentials \
  --server "$SERVER" \
  --realm master \
  --user "$KC_ADMIN_USER" \
  --password "$KC_ADMIN_PASS" >/dev/null
green "  ✓ logged in"

blue "[2/4] Patching master realm sslRequired → NONE …"
docker exec "$KC_CONTAINER" "$KCADM" update realms/master -s sslRequired=NONE
green "  ✓ master realm patched"

blue "[3/4] Patching $REALM realm sslRequired → NONE …"
if docker exec "$KC_CONTAINER" "$KCADM" get "realms/$REALM" >/dev/null 2>&1; then
  docker exec "$KC_CONTAINER" "$KCADM" update "realms/$REALM" -s sslRequired=NONE
  green "  ✓ $REALM realm patched"
else
  yellow "  ! Realm '$REALM' not found. Run: cd backend/setup/keycloak && python3 setup_realm.py"
fi

blue "[4/4] Verifying with a real direct-grant call …"
RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://localhost:8080/realms/$REALM/protocol/openid-connect/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=password' \
  --data-urlencode 'client_id=datasharing-backend' \
  --data-urlencode 'client_secret=dev-client-secret' \
  --data-urlencode 'username=sara.fin@acme.local' \
  --data-urlencode 'password=Test123!' \
  || true)

case "$RESP" in
  200) green "  ✓ direct-grant returned 200 — login is working end-to-end." ;;
  401) yellow "  ! sslRequired fixed, but credentials are wrong (HTTP 401)."
       yellow "    Run: bash scripts/diagnose_login.sh sara.fin@acme.local Test123!"
       ;;
  403) red   "  ✗ Still 403. The patch did not take, or sslRequired is enforced elsewhere."
       red   "    Try restarting the container: docker compose -f docker-compose.dev.yml restart keycloak"
       ;;
  *)   yellow "  ! direct-grant returned HTTP $RESP — check Keycloak logs:"
       yellow "    docker logs $KC_CONTAINER --tail=50"
       ;;
esac

echo
green "Done. Now open http://localhost:3001/login and try sara.fin@acme.local / Test123!"
