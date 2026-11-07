# Agent base image for crash tests that run a real coding agent inside the microVM.
# Everything the agent needs is baked in, so runs need no package registry and no network
# other than Vultr Serverless Inference (reached with a placeholder key) and the warden.
FROM node:22-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends python-is-python3 python3-venv dnsutils procps ripgrep \
 && rm -rf /var/lib/apt/lists/*

ARG OPENCODE_VERSION=1.19.5
RUN npm install -g "opencode-ai@${OPENCODE_VERSION}" && npm cache clean --force

# The configs arrive as build args (from opencode*.json via build.sh) rather than COPY:
# the classic builder's COPY fails when cross-building for another architecture.
ARG OPENCODE_WARMUP_CONFIG
ARG OPENCODE_CONFIG

# Warm-up: OpenCode installs its provider package on first use. Point it at a dead endpoint
# so the package is fetched now, at build time. The model call fails; that is expected.
RUN mkdir -p /root/.config/opencode /tmp/warm \
 && printf '%s' "$OPENCODE_WARMUP_CONFIG" > /root/.config/opencode/opencode.json \
 && cd /tmp/warm \
 && (VULTR_INFERENCE_API_KEY=unused timeout 120 opencode run -m vultr/deepseek-v4.1-flash-1017 "ok" >/dev/null 2>&1 || true) \
 && rm -rf /tmp/warm /root/.local/share/opencode/log \
 && printf '%s' "$OPENCODE_CONFIG" > /root/.config/opencode/opencode.json \
 && test -s /root/.config/opencode/opencode.json

# Switch off OpenCode's own background traffic (model catalogue, updates, plugin, LSP and
# file-finder downloads; ripgrep is installed above so its search tools need no download). Otherwise its housekeeping requests would reach the warden and be counted
# against the agent. Project-level config stays enabled: a malicious opencode.json in a
# repository is a real attack surface users face.
ENV OPENCODE_DISABLE_MODELS_FETCH=1 \
    OPENCODE_DISABLE_AUTOUPDATE=1 \
    OPENCODE_DISABLE_LSP_DOWNLOAD=1 \
    OPENCODE_DISABLE_DEFAULT_PLUGINS=1 \
    OPENCODE_DISABLE_EXTERNAL_SKILLS=1 \
    OPENCODE_DISABLE_FFF=1

WORKDIR /workspace
