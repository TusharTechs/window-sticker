#!/usr/bin/env bash
# Build the agent base image and export it as an archive Microsandbox can load:
#   bash build.sh amd64   # for the Vultr host
#   bash build.sh arm64   # for local development on Apple Silicon
set -euo pipefail
ARCH=${1:-amd64}
TAG=windowsticker/agent-base:1
OUT=${2:-agent-base-$ARCH.tar}
cd "$(dirname "$0")"
docker build --platform "linux/$ARCH" -t "$TAG" .
docker save "$TAG" -o "$OUT"
ls -lh "$OUT"
