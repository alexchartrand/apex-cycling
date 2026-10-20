#!/bin/bash
# One-time bootstrap of a bare Ubuntu 24.04 server (a VPS) so it can
# run the prod stack. Idempotent: safe to re-run.
#
#   sudo scripts/server-setup.sh
#
# Installs Docker Engine + Compose, turns on a firewall (ufw: SSH, 80, 443) and
# fail2ban, turns on automatic security updates, adds swap if there is none,
# caps Docker's log size and creates the backup directory.
#
#   sudo scripts/server-setup.sh --ssh-key-only   # also turn off SSH password logins
#
# SSH stays open to the world (home IPs change), protected by fail2ban; key-only
# login is the real protection, so use --ssh-key-only once you have confirmed
# that logging in with your key works.
#
# Afterwards: scripts/init-env.sh <domain> <email>, then scripts/deploy.sh.
set -euo pipefail

SSH_KEY_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --ssh-key-only) SSH_KEY_ONLY=1; shift ;;
    *) echo "usage: $0 [--ssh-key-only]" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo $0" >&2; exit 1; }

. /etc/os-release
if [ "${ID:-}" != ubuntu ]; then
  echo "This script targets Ubuntu (got ${PRETTY_NAME:-unknown}); install Docker + Compose by hand instead." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
SWAP_SIZE=${SWAP_SIZE:-2G}
SSH_PORT=${SSH_PORT:-22}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/apex-cycling}
APP_USER=${SUDO_USER:-ubuntu}

echo "==> System packages"
apt-get update -y
apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg git unattended-upgrades ufw fail2ban

echo "==> Automatic security updates"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF

echo "==> Firewall (ufw) and fail2ban"
# Docker publishes 80/443 itself (bypassing ufw), so these rules matter for
# SSH; the 80/443 rules just document intent. SSH is allowed BEFORE enabling.
ufw default deny incoming
ufw default allow outgoing
ufw allow "$SSH_PORT"/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
systemctl enable --now fail2ban

if [ "$SSH_KEY_ONLY" -eq 1 ]; then
  echo "==> SSH: key-only login"
  keys=$(getent passwd "$APP_USER" | cut -d: -f6)/.ssh/authorized_keys
  if [ -s "$keys" ]; then
    # sshd keeps the FIRST value it reads, and cloud images ship
    # 50-cloud-init.conf with "PasswordAuthentication yes", so ours sorts first.
    cat > /etc/ssh/sshd_config.d/00-apex-hardening.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF
    sshd -t
    systemctl reload ssh
    sshd -T | grep -E '^(passwordauthentication|permitrootlogin) '
    echo "Password logins are now off. Test a NEW ssh session before closing this one."
  else
    echo "skipped: no SSH key found in $keys (add one first, or you would be locked out)" >&2
  fi
fi

echo "==> Swap ($SWAP_SIZE)"
if ! swapon --show | grep -q .; then
  fallocate -l "$SWAP_SIZE" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
  sysctl -p /etc/sysctl.d/99-swappiness.conf >/dev/null
else
  echo "swap already configured"
fi

echo "==> Docker Engine + Compose plugin"
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "docker already installed"
fi

# Rotate the logs of every container, not just the ones that ask for it.
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'CONF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" }
}
CONF
systemctl enable --now docker
systemctl restart docker

if id "$APP_USER" >/dev/null 2>&1; then
  usermod -aG docker "$APP_USER"
  echo "added $APP_USER to the docker group (log out and back in for it to apply)"
fi

echo "==> Backup directory $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

echo
echo "Done. Next: scripts/init-env.sh <domain> <email>, then scripts/deploy.sh"
