#!/usr/bin/env bash
# renew-certs.sh
# Weekly cron renewal. Uses webroot so nginx keeps running.
# If a renewal happened, copies fresh certs to nginx/certs and reloads nginx.
#
# Cron: 0 3 * * 1 /opt/datasharing/scripts/renew-certs.sh >> /var/log/datasharing-renew.log 2>&1

set -euo pipefail

: "${DOMAIN_ROOT:?set DOMAIN_ROOT in env}"

APP_DIR="/opt/datasharing"
WEBROOT="${APP_DIR}/nginx/webroot"
CERT_DST="${APP_DIR}/nginx/certs"

# Capture existing cert serial so we can detect rotation
OLD_SERIAL="$(openssl x509 -in "${CERT_DST}/fullchain.pem" -noout -serial 2>/dev/null || true)"

docker run --rm \
  -v "${WEBROOT}:/var/www/certbot" \
  -v "/etc/letsencrypt:/etc/letsencrypt" \
  -v "/var/log/letsencrypt:/var/log/letsencrypt" \
  certbot/certbot:latest renew --webroot -w /var/www/certbot --quiet

NEW_FULLCHAIN="/etc/letsencrypt/live/${DOMAIN_ROOT}/fullchain.pem"
NEW_PRIVKEY="/etc/letsencrypt/live/${DOMAIN_ROOT}/privkey.pem"

if [[ -f "$NEW_FULLCHAIN" ]]; then
  NEW_SERIAL="$(openssl x509 -in "$NEW_FULLCHAIN" -noout -serial 2>/dev/null || true)"
  if [[ "$NEW_SERIAL" != "$OLD_SERIAL" ]]; then
    echo "$(date -Iseconds) cert rotated: $OLD_SERIAL -> $NEW_SERIAL"
    install -m 0644 "$NEW_FULLCHAIN" "${CERT_DST}/fullchain.pem"
    install -m 0600 "$NEW_PRIVKEY"   "${CERT_DST}/privkey.pem"
    (cd "$APP_DIR" && \
      docker compose -f docker-compose.prod.yml --env-file .env.prod \
        exec -T nginx nginx -s reload)
  else
    echo "$(date -Iseconds) renew ran, no rotation needed"
  fi
fi
