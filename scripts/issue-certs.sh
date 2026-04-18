#!/usr/bin/env bash
# issue-certs.sh
# First-time Let's Encrypt issuance using webroot (so we never have to stop nginx again).
#
# Prereqs:
#   - DNS A records for all three subdomains point to this VM
#   - nginx is running with nginx-bootstrap.conf (HTTP-only, serves /.well-known/acme-challenge/)
#   - /opt/datasharing/nginx/webroot exists and is mounted into the nginx container
#
# Usage:
#   sudo DOMAIN_ROOT=datasharing.sa ADMIN_EMAIL=admin@datasharing.sa ./issue-certs.sh

set -euo pipefail

: "${DOMAIN_ROOT:?set DOMAIN_ROOT, e.g. datasharing.sa}"
: "${ADMIN_EMAIL:?set ADMIN_EMAIL, e.g. admin@datasharing.sa}"

APP_DIR="/opt/datasharing"
WEBROOT="${APP_DIR}/nginx/webroot"
CERT_DST="${APP_DIR}/nginx/certs"

mkdir -p "$WEBROOT" "$CERT_DST"

# Run certbot in a throwaway container sharing the webroot volume.
docker run --rm \
  -v "${APP_DIR}/nginx/webroot:/var/www/certbot" \
  -v "/etc/letsencrypt:/etc/letsencrypt" \
  -v "/var/log/letsencrypt:/var/log/letsencrypt" \
  certbot/certbot:latest certonly \
    --webroot -w /var/www/certbot \
    -d "${DOMAIN_ROOT}" \
    -d "www.${DOMAIN_ROOT}" \
    -d "api.${DOMAIN_ROOT}" \
    -d "auth.${DOMAIN_ROOT}" \
    --email "${ADMIN_EMAIL}" --agree-tos --no-eff-email --non-interactive

# Copy certs into the nginx volume with the names nginx.conf expects
install -m 0644 "/etc/letsencrypt/live/${DOMAIN_ROOT}/fullchain.pem" "${CERT_DST}/fullchain.pem"
install -m 0600 "/etc/letsencrypt/live/${DOMAIN_ROOT}/privkey.pem"   "${CERT_DST}/privkey.pem"
chown -R "$(id -u):$(id -g)" "${CERT_DST}"

echo "Certs issued and staged at ${CERT_DST}"
echo "Next: restore the TLS nginx.conf (cp nginx/nginx.conf.tls.bak nginx/nginx.conf),"
echo "then: docker compose -f docker-compose.prod.yml exec nginx nginx -s reload"
