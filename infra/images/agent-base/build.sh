#!/usr/bin/env bash
# Build the agent base image and export it as an archive Microsandbox can load:
#   bash build.sh amd64   # for the Vultr host
#   bash build.sh arm64   # for local development on Apple Silicon
set -euo pipefail
ARCH=${1:-amd64}
# Per-architecture tag: the classic builder otherwise reuses a cached base of the wrong arch.
TAG=windowsticker/agent-base:1-$ARCH
OUT=${2:-agent-base-$ARCH.tar}
cd "$(dirname "$0")"
docker build --pull --platform "linux/$ARCH" -t "$TAG" \
  --build-arg OPENCODE_WARMUP_CONFIG="$(cat opencode.warmup.json)" \
  --build-arg OPENCODE_CONFIG="$(cat opencode.json)" .
docker save "$TAG" -o "$OUT"
ls -lh "$OUT"
