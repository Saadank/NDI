#!/usr/bin/env bash
# End-to-end backend smoke test for the Datarix data-sharing wizard.
#
# Walks the same path the frontend takes:
#   1. Login (POST /api/v1/platform/auth/login)
#   2. List receiver departments (GET /api/v1/platform/groups/)
#   3. Create draft request (POST /api/v1/products/data-sharing/requests/)
#   4. Initiate file upload (POST /api/v1/products/data-sharing/files/initiate)
#   5. Complete file upload (PUT  /api/v1/products/data-sharing/files/{id}/upload)
#   6. Submit (POST /api/v1/products/data-sharing/requests/{id}/submit)
#   7. List requests so you can see the new one
#
# Run from your Mac (NOT from the sandbox):
#   bash scripts/e2e_login_to_submit.sh
#
# Override credentials/host with env vars if needed:
#   API=http://localhost:8000 USER=ahmed@acme.local PASS=Test123! \
#     bash scripts/e2e_login_to_submit.sh

set -euo pipefail

API="${API:-http://localhost:8000}"
USER_EMAIL="${USER:-ahmed@acme.local}"
PASS="${PASS:-Test123!}"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
blue()  { printf "\033[34m%s\033[0m\n" "$*"; }

# Tiny JSON pretty-printer (Python is everywhere on macOS).
pp() { python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))' 2>/dev/null || cat; }

# Tiny JSON field extractor (no jq dependency).
jq_field() {
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d$1)" 2>/dev/null || true
}

blue "[1/7] Logging in as $USER_EMAIL …"
LOGIN_BODY=$(printf '{"username":"%s","password":"%s"}' "$USER_EMAIL" "$PASS")
LOGIN_RESP=$(curl -fsS -X POST "$API/api/v1/platform/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$LOGIN_BODY") || { red "Login failed"; exit 1; }

ACCESS=$(echo "$LOGIN_RESP" | jq_field '["access_token"]')
if [ -z "$ACCESS" ] || [ "$ACCESS" = "None" ]; then red "No access_token in login response"; echo "$LOGIN_RESP" | pp; exit 1; fi
USER_GROUP_ID=$(echo "$LOGIN_RESP" | jq_field '["user"].get("group_id")')
TENANT_ID=$(echo "$LOGIN_RESP" | jq_field '["user"]["tenant_id"]')
green "  ✓ logged in (user.group_id=$USER_GROUP_ID, tenant_id=$TENANT_ID)"

blue "[2/7] Listing groups (receiver department dropdown source) …"
GROUPS=$(curl -fsS -H "Authorization: Bearer $ACCESS" "$API/api/v1/platform/groups/")
echo "$GROUPS" | python3 -c '
import json, sys, os
data=json.load(sys.stdin)
my=str(os.environ.get("USER_GROUP_ID","None"))
print(f"  Found {len(data)} group(s):")
for g in data:
  marker = " (mine)" if str(g.get("id"))==my else ""
  print(f"    [{g[\"id\"]:>3}] {g[\"name\"]} — slug={g[\"slug\"]} active={g[\"is_active\"]}{marker}")
' USER_GROUP_ID="$USER_GROUP_ID"

# Pick a receiver group that is NOT the requester's own (EC-01).
RECEIVER_ID=$(echo "$GROUPS" | python3 -c "
import json,sys,os
mine=str(os.environ.get('MINE','None'))
for g in json.load(sys.stdin):
  if g.get('is_active') and str(g.get('id'))!=mine:
    print(g['id']); break
" MINE="$USER_GROUP_ID")
if [ -z "$RECEIVER_ID" ]; then red "No eligible receiver group found (need a 2nd active group in your tenant)"; exit 1; fi
green "  ✓ will use receiver_group_id=$RECEIVER_ID"

blue "[3/7] Creating draft share request …"
DRAFT_BODY=$(cat <<JSON
{
  "title": "E2E smoke test $(date +%s)",
  "purpose": "Automated end-to-end verification",
  "legal_basis": "contract",
  "sharing_type": "internal",
  "data_classification": "internal",
  "personal_data_involved": false,
  "data_type": "file",
  "delivery_channel": "portal",
  "receiver_group_id": $RECEIVER_ID,
  "dpia_confirmed": false
}
JSON
)
DRAFT=$(curl -fsS -X POST "$API/api/v1/products/data-sharing/requests/" \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d "$DRAFT_BODY") || { red "Create draft failed"; exit 1; }
REQ_ID=$(echo "$DRAFT" | jq_field '["id"]')
REQ_NUM=$(echo "$DRAFT" | jq_field '["request_number"]')
green "  ✓ draft created: $REQ_NUM (id=$REQ_ID)"

blue "[4/7] Initiating file upload …"
TMP=$(mktemp -t datarix-e2e.XXXXXX.txt)
echo "Datarix E2E test file - $(date)" > "$TMP"
SIZE=$(wc -c < "$TMP" | tr -d ' ')
HASH=$(shasum -a 256 "$TMP" | awk '{print $1}')
INIT_BODY=$(cat <<JSON
{
  "request_id": "$REQ_ID",
  "filename": "$(basename "$TMP")",
  "size": $SIZE,
  "mime_type": "text/plain",
  "sha256_hash": "$HASH"
}
JSON
)
INITIATED=$(curl -fsS -X POST "$API/api/v1/products/data-sharing/files/initiate" \
  -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d "$INIT_BODY") || { red "Initiate failed"; exit 1; }
FILE_ID=$(echo "$INITIATED" | jq_field '["id"]')
green "  ✓ file row created: $FILE_ID (status=$(echo "$INITIATED" | jq_field '["status"]'))"

blue "[5/7] Uploading file bytes (multipart PUT) …"
UPLOADED=$(curl -fsS -X PUT "$API/api/v1/products/data-sharing/files/$FILE_ID/upload?sha256_hash=$HASH" \
  -H "Authorization: Bearer $ACCESS" \
  -F "file=@$TMP") || { red "Upload failed"; exit 1; }
green "  ✓ upload complete (status=$(echo "$UPLOADED" | jq_field '["status"]'))"
rm -f "$TMP"

blue "[6/7] Submitting request …"
SUBMITTED=$(curl -fsS -X POST "$API/api/v1/products/data-sharing/requests/$REQ_ID/submit" \
  -H "Authorization: Bearer $ACCESS") || { red "Submit failed"; exit 1; }
green "  ✓ submitted (status=$(echo "$SUBMITTED" | jq_field '["status"]'), workflow_template_id=$(echo "$SUBMITTED" | jq_field '["workflow_template_id"]'))"

blue "[7/7] Listing my requests …"
LIST=$(curl -fsS -H "Authorization: Bearer $ACCESS" "$API/api/v1/products/data-sharing/requests/?page=1&limit=5")
echo "$LIST" | python3 -c '
import json, sys
d=json.load(sys.stdin)
items=d.get("data",[])
print(f"  Recent requests ({len(items)} shown):")
for r in items:
  print(f"    {r[\"request_number\"]:<14} [{r[\"status\"]:>10}] {r[\"title\"]}")
'

green "\nAll backend hops passed. If this script is green, the backend side of the wizard is healthy — any remaining issue is purely in the frontend (open DevTools, repeat the flow at http://localhost:3001/data-sharing/new)."
