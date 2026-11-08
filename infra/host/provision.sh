#!/usr/bin/env bash
# One-time (idempotent) system setup for a Window Sticker host. Run as root.
#   WSK_DOMAIN=<public hostname> bash provision.sh
set -euo pipefail
: "${WSK_DOMAIN:?set WSK_DOMAIN}"
APP=/home/wsk/window-sticker
export DEBIAN_FRONTEND=noninteractive

echo "==> packages"
apt-get -qq update
apt-get -qq install -y postgresql debian-keyring debian-archive-keyring apt-transport-https curl gnupg ufw >/dev/null

echo "==> app user (runs every service; in the kvm group for microVMs)"
[[ -e /dev/kvm ]] || { echo "/dev/kvm is missing: use a KVM-capable VX1 plan" >&2; exit 1; }
if ! id wsk >/dev/null 2>&1; then
  useradd -m -s /bin/bash -G kvm wsk
  install -d -m 700 -o wsk -g wsk /home/wsk/.ssh
  [[ -f /root/.ssh/authorized_keys ]] && install -m 600 -o wsk -g wsk /root/.ssh/authorized_keys /home/wsk/.ssh/
fi
usermod -aG kvm wsk
[[ -d "$APP" ]] || { echo "copy the code to $APP first (see README, Deployment)" >&2; exit 1; }
chown -R wsk:wsk /home/wsk
chmod 700 /home/wsk  # Microsandbox refuses a storage root other accounts can read
sudo -u wsk -H bash -c 'command -v ~/.local/bin/uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh' >/dev/null
sudo -u wsk -H bash -c 'command -v ~/.local/bin/msb >/dev/null || curl -fsSL https://install.microsandbox.dev | sh' >/dev/null

if ! command -v node >/dev/null || [[ "$(node -v)" != v22* ]]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
  apt-get -qq install -y nodejs >/dev/null
fi
command -v pnpm >/dev/null || npm install -g pnpm@9 >/dev/null 2>&1

if ! command -v caddy >/dev/null; then
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get -qq update && apt-get -qq install -y caddy >/dev/null
fi

echo "==> host firewall (defence in depth behind the Vultr firewall group)"
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "==> postgres (local only)"
ENV_FILE="$APP/.env"
touch "$ENV_FILE"; chown wsk:wsk "$ENV_FILE"; chmod 600 "$ENV_FILE"
if ! grep -q '^WSK_DATABASE_URL=' "$ENV_FILE"; then
  PW=$(openssl rand -hex 24)
  sudo -u postgres psql -qtc "SELECT 1 FROM pg_roles WHERE rolname='windowsticker'" | grep -q 1 \
    && sudo -u postgres psql -qc "ALTER ROLE windowsticker PASSWORD '$PW'" \
    || sudo -u postgres psql -qc "CREATE ROLE windowsticker LOGIN PASSWORD '$PW'"
  sudo -u postgres psql -qtc "SELECT 1 FROM pg_database WHERE datname='windowsticker'" | grep -q 1 \
    || sudo -u postgres createdb -O windowsticker windowsticker
  echo "WSK_DATABASE_URL=postgresql+asyncpg://windowsticker:$PW@127.0.0.1:5432/windowsticker" >> "$ENV_FILE"
fi
grep -q '^WSK_ADMIN_TOKEN=' "$ENV_FILE" || echo "WSK_ADMIN_TOKEN=$(openssl rand -hex 24)" >> "$ENV_FILE"

echo "==> services"
install -m 644 "$APP/infra/host/systemd/"wsk-*.service /etc/systemd/system/
install -m 644 "$APP/infra/host/Caddyfile" /etc/caddy/Caddyfile
mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironment=WSK_DOMAIN=%s\n' "$WSK_DOMAIN" > /etc/systemd/system/caddy.service.d/domain.conf
# The web app needs its public URL for link previews; it never reads the secrets file.
mkdir -p /etc/systemd/system/wsk-web.service.d
printf '[Service]\nEnvironment=WSK_PUBLIC_URL=https://%s\n' "$WSK_DOMAIN" > /etc/systemd/system/wsk-web.service.d/public-url.conf
systemctl daemon-reload
systemctl enable -q wsk-api wsk-worker wsk-web caddy
echo "==> provisioned for https://$WSK_DOMAIN"
