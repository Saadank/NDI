#!/usr/bin/env bash
# restore-drill.sh
# Monthly DR drill: pulls the latest backup from Object Storage, restores into
# a throwaway Postgres, verifies a sample query, tears down.
#
# Intentionally does NOT touch production. Run on the VM or a separate box.
#
# Usage:
#   BUCKET=datasharing-backups ./restore-drill.sh

set -euo pipefail

BUCKET="${BUCKET:-datasharing-backups}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; docker rm -f pg-drill >/dev/null 2>&1 || true' EXIT

echo "==> Finding latest app backup"
LATEST=$(oci os object list --bucket-name "$BUCKET" --prefix "app_" \
          --all --query 'data[*].name' --raw-output \
          | jq -r '.[]' | sort | tail -n1)
echo "Latest app backup: $LATEST"

oci os object get --bucket-name "$BUCKET" --name "$LATEST" --file "$TMP/app.pgdump.gz"

echo "==> Booting throwaway postgres"
docker run -d --rm --name pg-drill \
  -e POSTGRES_PASSWORD=drill \
  -e POSTGRES_DB=drill \
  -e POSTGRES_USER=drill \
  postgres:15-alpine >/dev/null
for i in {1..20}; do
  docker exec pg-drill pg_isready -U drill && break
  sleep 2
done

echo "==> Restoring"
gunzip -c "$TMP/app.pgdump.gz" | docker exec -i pg-drill pg_restore -U drill -d drill --no-owner --no-acl

echo "==> Sampling schema"
docker exec pg-drill psql -U drill -d drill -c "\dt" | head -20

echo "==> Drill passed"
