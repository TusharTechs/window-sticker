"""Microsandbox driver: one libkrun microVM (own kernel) per run, on a KVM host.

This is the isolation tier Vultr's own agent-sandboxing guide uses on VX1 instances.
Verified against microsandbox 0.7.13 (see docs/MEASUREMENTS.md):

* the network policy denies all egress by default; DNS is not allowed at all;
* the only open path is TCP to ``host.microsandbox.internal`` on the run's warden port,
  and the guest is told to use it through the standard proxy variables;
* the runtime itself refuses direct connections, private ranges and metadata (403);
* ``max_duration`` makes the runtime kill the VM even if the harness hangs.
"""

from __future__ import annotations

import contextlib
import importlib
import shlex
import socket
import time
from typing import Any

from windowsticker.sandbox.base import ExecResult, SandboxSpec

# The SDK is optional so the rest of the package installs (and type-checks) anywhere.
msb: Any
try:
    msb = importlib.import_module("microsandbox")
except ImportError:  # pragma: no cover - exercised only where the SDK is missing
    msb = None


def _require_sdk() -> Any:
    if msb is None:
        raise RuntimeError(
            "The microsandbox SDK is not installed. Install with `uv sync --extra sandbox` "
            "on a KVM-capable host (see infra/host/bootstrap.sh)."
        )
    return msb


def build_network(spec: SandboxSpec) -> Any:
    """Deny everything, then allow exactly one TCP port on the host: the Egress Warden."""
    sdk = _require_sdk()
    rules: list[Any] = []
    if spec.network.allow_dns or spec.network.direct:
        rules += list(sdk.Rule.allow_dns())
    for target in spec.network.direct:
        host, _, port = target.rpartition(":")
        rules.append(
            sdk.Rule.allow(
                destination=sdk.Destination.domain(host), protocol=sdk.Protocol.TCP, port=int(port)
            )
        )
    for host_port in spec.network.host_ports:
        rules.append(
            sdk.Rule.allow(
                destination=sdk.Destination.group(sdk.DestGroup.HOST),
                protocol=sdk.Protocol.TCP,
                port=host_port,
            )
        )
    if spec.network.warden_host:
        _, _, port = spec.network.warden_host.rpartition(":")
        rules.append(
            sdk.Rule.allow(
                destination=sdk.Destination.group(sdk.DestGroup.HOST),
                protocol=sdk.Protocol.TCP,
                port=int(port),
            )
        )
    policy = sdk.NetworkPolicy(
        default_egress=sdk.Action.DENY,
        default_ingress=sdk.Action.DENY,
        rules=tuple(rules),
    )
    if spec.network.direct and not spec.network.dns_resolver:
        raise ValueError("direct destinations need the warden DNS lane (dns_resolver)")
    dns = None
    if spec.network.dns_resolver:
        # DnsConfig lives in microsandbox.types and is not re-exported at the top level.
        from microsandbox.types import DnsConfig

        dns = DnsConfig(nameservers=(spec.network.dns_resolver,))
    return sdk.Network(policy=policy, dns=dns)


def build_secrets(spec: SandboxSpec) -> list[Any]:
    # The violation action is set once on the sandbox (see create()); the per-secret
    # argument is rejected by microsandbox 0.7.13's native layer.
    sdk = _require_sdk()
    return [sdk.Secret.env(s.env, value=s.value, allow=list(s.allow_hosts)) for s in spec.secrets]


def proxy_env(warden_host: str, direct: tuple[str, ...] = ()) -> dict[str, str]:
    url = f"http://{warden_host}"
    env = {}
    for name in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env[name] = url
    # The host's own lanes (inference lane) are reached directly, never through the warden.
    bypass = ["host.microsandbox.internal", *(t.rpartition(":")[0] for t in direct)]
    env["no_proxy"] = env["NO_PROXY"] = ",".join(bypass)
    return env


class MicrosandboxSandbox:
    def __init__(self, handle: Any, name: str) -> None:
        self._sb = handle
        self._name = name
        self._host = socket.gethostname()
        self._alive = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def host_id(self) -> str:
        return self._host

    async def exec(self, command: str, *, timeout_s: float, cwd: str | None = None) -> ExecResult:
        sdk = _require_sdk()
        started = time.perf_counter()
        try:
            out = await self._sb.shell(command, cwd=cwd, timeout=timeout_s)
        except sdk.ExecTimeoutError:
            return ExecResult(None, "", "timed out", time.perf_counter() - started, timed_out=True)
        return ExecResult(
            exit_code=out.exit_code,
            stdout=out.stdout_text or "",
            stderr=out.stderr_text or "",
            duration_s=time.perf_counter() - started,
        )

    async def write_file(self, path: str, data: bytes, mode: str = "0644") -> None:
        parent = path.rsplit("/", 1)[0] or "/"
        await self._sb.shell(f"mkdir -p {shlex.quote(parent)}")
        await self._sb.fs.write(path, data)
        await self._sb.shell(f"chmod {shlex.quote(mode)} {shlex.quote(path)}")

    async def read_file(self, path: str) -> bytes:
        data: bytes = await self._sb.fs.read(path)
        return data

    async def destroy(self) -> None:
        if not self._alive:
            return
        self._alive = False
        sdk = _require_sdk()
        # Kill may race with a VM the runtime already terminated (secret violation or
        # max_duration), and remove may find it already gone; both are fine.
        with contextlib.suppress(Exception):
            await self._sb.kill(timeout=10)
        with contextlib.suppress(Exception):
            await sdk.Sandbox.remove(self._name)


class MicrosandboxDriver:
    kind = "microsandbox"

    async def create(self, spec: SandboxSpec) -> MicrosandboxSandbox:
        sdk = _require_sdk()
        env = dict(spec.env)
        if spec.network.warden_host:
            env.update(proxy_env(spec.network.warden_host, spec.network.direct))
        kwargs: dict[str, Any] = {
            # The managed root disk caps how much the guest can write to the host's disk.
            "image": sdk.Image.oci(spec.image, root_disk=spec.disk_mib),
            "cpus": spec.cpus,
            "memory": spec.memory_mib,
            "network": build_network(spec),
            "replace": True,
            "env": env,
            "labels": dict(spec.labels),
        }
        if spec.max_duration_s:
            kwargs["max_duration"] = spec.max_duration_s
        if spec.intercept_tls:
            kwargs["intercept_tls"] = True
        if spec.secrets:
            kwargs["secrets"] = build_secrets(spec)
            kwargs["secret_violation_action"] = sdk.ViolationAction.BLOCK_AND_TERMINATE
        handle = await sdk.Sandbox.create(spec.name, **kwargs)
        return MicrosandboxSandbox(handle, spec.name)

    async def live(self, label_key: str, label_value: str) -> list[str]:
        sdk = _require_sdk()
        page = await sdk.Sandbox.list_with(labels={label_key: label_value})
        return [h.name for h in page.sandboxes]
