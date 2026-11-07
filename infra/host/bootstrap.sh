#!/usr/bin/env bash
# Prepare a fresh Vultr VX1 (Ubuntu 24.04) instance as a Window Sticker sandbox host.
# Follows Vultr's guide: https://docs.vultr.com/how-to-set-up-agent-sandboxing-on-vultr-cloud-compute
# Run as a sudo-capable non-root user.
set -euo pipefail

echo "==> KVM"
if [[ ! -e /dev/kvm ]]; then
  echo "/dev/kvm is missing: this plan does not expose hardware virtualisation." >&2
  exit 1
fi
sudo usermod -aG kvm "$USER"

echo "==> base packages"
sudo apt-get update -y
sudo apt-get install -y git curl ca-certificates python3-venv build-essential

echo "==> uv"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

echo "==> microsandbox runtime"
if ! command -v msb >/dev/null; then
  curl -fsSL https://install.microsandbox.dev | sh
fi

echo "==> done. Log out and back in (for the kvm group and PATH), then run:"
echo "    msb doctor"
echo "    cd window-sticker/backend && uv sync --extra sandbox"
echo "    uv run windowsticker probe sandbox"
