#!/usr/bin/env bash
# bootstrap-vm.sh
# Idempotent first-boot setup for the OCI Ampere A1 Ubuntu 22.04 VM.
# Run as the default `ubuntu` user. Safe to re-run.
#
# Covers: iptables fix, OS updates, Docker, fail2ban, timezone,
#         unattended upgrades, OCI CLI install, and a /opt/datasharing home.
set -euo pipefail

log() { printf "\n\033[1;34m==> %s\033[0m\n" "$*"; }

if [[ $(id -u) -eq 0 ]]; then
  echo "Run as the 'ubuntu' user, not root. Use sudo inside the script." >&2
  exit 1
fi

log "1/8  Fix OCI Ubuntu iptables DROP (80/443)"
sudo iptables -C INPUT -m state --state NEW -p tcp --dport 80  -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80  -j ACCEPT
sudo iptables -C INPUT -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null \
  || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save

log "2/8  Apt update + baseline packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl wget ufw fail2ban unattended-upgrades ca-certificates \
  jq unzip netfilter-persistent

log "3/8  Timezone + unattended-upgrades"
sudo timedatectl set-timezone Asia/Riyadh
echo 'Unattended-Upgrade::Automatic-Reboot "false";' | sudo tee /etc/apt/apt.conf.d/51unattended-upgrades-local >/dev/null
sudo systemctl enable --now unattended-upgrades
sudo systemctl enable --now fail2ban

log "4/8  Docker engine + compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

log "5/8  OCI CLI (for backups + automation)"
if ! command -v oci >/dev/null 2>&1; then
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)" \
    -- --accept-all-defaults
fi

log "6/8  App directories"
sudo mkdir -p /opt/datasharing /opt/backups /var/log/datasharing
sudo chown -R "$USER":"$USER" /opt/datasharing /opt/backups
sudo chown -R root:adm /var/log/datasharing
sudo chmod 750 /var/log/datasharing

log "7/8  MinIO client (mc) for consistent bucket backups"
if ! command -v mc >/dev/null 2>&1; then
  ARCH=$(uname -m)
  case "$ARCH" in
    aarch64|arm64) MC_URL="https://dl.min.io/client/mc/release/linux-arm64/mc" ;;
    x86_64)        MC_URL="https://dl.min.io/client/mc/release/linux-amd64/mc" ;;
    *) echo "Unsupported arch: $ARCH"; exit 1 ;;
  esac
  sudo curl -fsSL -o /usr/local/bin/mc "$MC_URL"
  sudo chmod +x /usr/local/bin/mc
fi

log "8/8  Summary"
docker --version
docker compose version
oci --version || true
mc --version | head -n1
echo
echo "Bootstrap complete. Log out/in once for the docker group to take effect."
