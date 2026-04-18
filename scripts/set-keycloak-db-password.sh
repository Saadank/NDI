#!/usr/bin/env bash
# set-keycloak-db-password.sh
# Run ONCE after the first `docker compose up -d postgres` on a fresh deployment.
# It replaces the bootstrap placeholder password created by 00_init_keycloak_db.sql
# with the real KEYCLOAK_DB_PASSWORD from .env.prod.

set -euo pipefail
cd /opt/datasharing
# shellcheck disable=SC1091
source .env.prod

docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U "$POSTGRES_USER" -d postgres -c \
  "ALTER ROLE keycloak WITH PASSWORD '${KEYCLOAK_DB_PASSWORD}';"

echo "keycloak DB role password set."
