#!/usr/bin/env bash
# Build and (re)start the app. Run as the wsk user after syncing the code.
set -euo pipefail
APP=$HOME/window-sticker
export PATH=$HOME/.local/bin:$PATH

echo "==> backend"
cd "$APP/backend" && uv sync --extra sandbox --no-dev -q

echo "==> web"
cd "$APP/web"
pnpm install --frozen-lockfile --silent
NODE_ENV=production pnpm build >/tmp/wsk-web-build.log 2>&1 || { tail -40 /tmp/wsk-web-build.log; exit 1; }
cp -r .next/static .next/standalone/.next/static
[ -d public ] && cp -r public .next/standalone/public || true
echo "==> built"
