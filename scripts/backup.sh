#!/usr/bin/env bash
# backup.sh
# Daily backup:
#   1. pg_dump of app DB
#   2. pg_dump of keycloak DB
#   3. consistent MinIO mirror via `mc` (not a volume tar)
#   4. upload to OCI Object Storage bucket
#   5. prune local backups > 7d
#   6. write a heartbeat object so an alarm can alert if backups stop
#
# Cron: 15 2 * * * /opt/datasharing/scripts/backup.sh >> /var/log/datasharing-backup.log 2>&1

set -euo pipefail

APP_DIR="/opt/datasharing"
cd "$APP_DIR"
# shellcheck disable=SC1091
source .env.prod

BUCKET="${BACKUP_BUCKET:-datasharing-backups}"
BDIR="/opt/backups"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[backup ${TS}]"

mkdir -p "$BDIR"

fail() {
  echo "$LOG_PREFIX FAILED: $*" >&2
  # Best-effort: write a failure marker so alarms notice
  echo "$(date -Iseconds) $*" | \
    oci os object put --bucket-name "$BUCKET" \
      --name "heartbeat/LAST_FAILURE_${TS}.txt" \
      --file /dev/stdin --force || true
  exit 1
}

trap 'fail "unexpected error at line $LINENO"' ERR

echo "$LOG_PREFIX start"

# --- Postgres app DB -----------------------------------------------
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  | gzip > "${BDIR}/app_${TS}.pgdump.gz"

# --- Postgres keycloak DB ------------------------------------------
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$KEYCLOAK_DB_USER" -d keycloak --format=custom \
  | gzip > "${BDIR}/keycloak_${TS}.pgdump.gz"

# --- MinIO consistent mirror (not a raw volume tar) ----------------
# mc connects through the docker network via the compose service name
docker run --rm --network "${COMPOSE_PROJECT_NAME:-datasharing}_default" \
  -v "${BDIR}:/backup" \
  -e MC_HOST_minio="http://${MINIO_ACCESS_KEY}:${MINIO_SECRET_KEY}@minio:9000" \
  minio/mc:latest mirror --overwrite --remove --quiet \
    minio/"${MINIO_BUCKET}" "/backup/minio_${TS}/"
tar czf "${BDIR}/minio_${TS}.tar.gz" -C "${BDIR}" "minio_${TS}"
rm -rf "${BDIR}/minio_${TS}"

# --- Upload to OCI Object Storage ----------------------------------
for f in "${BDIR}/app_${TS}.pgdump.gz" \
         "${BDIR}/keycloak_${TS}.pgdump.gz" \
         "${BDIR}/minio_${TS}.tar.gz"; do
  oci os object put --bucket-name "$BUCKET" \
    --name "$(basename "$f")" --file "$f" --force
done

# --- Heartbeat: single object whose timestamp an alarm can check ---
echo "$(date -Iseconds) ok" | \
  oci os object put --bucket-name "$BUCKET" \
    --name "heartbeat/LAST_SUCCESS.txt" \
    --file /dev/stdin --force

# --- Prune local -------------------------------------------------------
find "$BDIR" -type f -mtime +7 -delete

echo "$LOG_PREFIX done"
