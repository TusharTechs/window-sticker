#!/usr/bin/env bash
# Build the agent base image and export it as an archive Microsandbox can load.
#   bash build.sh            # native architecture, with docker or podman
#   BUILDER=podman bash build.sh
# Build on a machine of the target architecture (the Vultr host for amd64): the classic
# docker builder silently ignores --platform when cross-building.
set -euo pipefail
cd "$(dirname "$0")"
BUILDER=${BUILDER:-$(command -v docker >/dev/null && echo docker || echo podman)}
ARCH=$(uname -m)
TAG=windowsticker/agent-base:1
OUT=${1:-agent-base-$ARCH.tar}

# Rootless podman on overlay storage leaks empty user.overlay.origin xattrs into layers,
# which Microsandbox's layer ingester rejects; the vfs driver writes clean layers.
if [ "$BUILDER" = podman ]; then
  # A separate storage root, so an existing overlay store is never touched.
  STORE=(--storage-driver=vfs --root "$HOME/.local/share/containers/vfs-storage")
  BUILD=(podman "${STORE[@]}" build)
  SAVE=(podman "${STORE[@]}" save --format docker-archive -o "$OUT" "$TAG")
else
  BUILD=(docker build)
  SAVE=(docker save "$TAG" -o "$OUT")
fi

"${BUILD[@]}" -t "$TAG" \
  --build-arg OPENCODE_WARMUP_CONFIG="$(cat opencode.warmup.json)" \
  --build-arg OPENCODE_CONFIG="$(cat opencode.json)" .

"${SAVE[@]}"
ls -lh "$OUT"
