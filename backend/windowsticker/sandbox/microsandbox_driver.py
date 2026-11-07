"""Microsandbox driver: one libkrun microVM (own kernel) per run, on a KVM host.

This is the isolation tier Vultr's own agent-sandboxing guide uses on VX1 instances.
Every option here maps to a documented SDK parameter:
https://docs.microsandbox.dev/sdk/python/sandbox.md
"""

from __future__ import annotations

import contextlib
import shlex
import socket
import time
from typing import Any

from windowsticker.sandbox.base import ExecResult, SandboxSpec

try:  # The SDK is optional so the rest of the package installs anywhere.
    import microsandbox as msb
except ImportError:  # pragma: no cover - exercised only where the SDK is missing
    msb = None


METADATA_CIDRS = ("169.254.0.0/16", "fd00:ec2::254/128", "100.100.100.200/32")


def _require_sdk() -> Any:
    if msb is None:
        raise RuntimeError(
            "The microsandbox SDK is not installed. Install with `uv sync --extra sandbox` "
            "on a KVM-capable host (see infra/host/bootstrap.sh)."
        )
    return msb


def build_network(spec: SandboxSpec) -> Any:
    """Deny-all egress, then allow exactly one TCP port on the host: the Egress Warden."""
    sdk = _require_sdk()
    rules: list[Any] = []
    # Explicit metadata denies come first so no later allow can ever reach them.
    if spec.network.block_metadata:
        rules += [sdk.Rule.deny(destination=cidr) for cidr in METADATA_CIDRS]
    if spec.network.allow_dns:
        rules += list(sdk.Rule.allow_dns())
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
    return sdk.Network(
        policy=policy, secret_violation_action=sdk.ViolationAction.BLOCK_AND_TERMINATE
    )


def build_secrets(spec: SandboxSpec) -> list[Any]:
    sdk = _require_sdk()
    out = []
    for s in spec.secrets:
        action = (
            sdk.ViolationAction.BLOCK_AND_TERMINATE
            if s.terminate_on_violation
            else sdk.ViolationAction.BLOCK_AND_LOG
        )
        out.append(
            sdk.Secret.env(s.env, value=s.value, allow=list(s.allow_hosts), violation_action=action)
        )
    return out


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
            exit_code=getattr(out, "exit_code", None),
            stdout=getattr(out, "stdout_text", "") or "",
            stderr=getattr(out, "stderr_text", "") or "",
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
        with contextlib.suppress(Exception):
            await self._sb.kill()
        sdk = _require_sdk()
        with contextlib.suppress(Exception):
            await sdk.Sandbox.remove(self._name)


class MicrosandboxDriver:
    kind = "microsandbox"

    def __init__(self, *, replace: bool = True) -> None:
        self._replace = replace

    async def create(self, spec: SandboxSpec) -> MicrosandboxSandbox:
        sdk = _require_sdk()
        kwargs: dict[str, Any] = {
            "image": spec.image,
            "cpus": spec.cpus,
            "memory": spec.memory_mib,
            "network": build_network(spec),
            "replace": self._replace,
        }
        if spec.secrets:
            kwargs["secrets"] = build_secrets(spec)
        if spec.env:
            kwargs["env"] = dict(spec.env)
        if spec.labels:
            kwargs["labels"] = dict(spec.labels)
        if spec.network.warden_host:
            kwargs["proxy"] = f"http://{spec.network.warden_host}"
        handle = await sdk.Sandbox.create(spec.name, **kwargs)
        return MicrosandboxSandbox(handle, spec.name)

    async def live(self, label_key: str, label_value: str) -> list[str]:
        sdk = _require_sdk()
        names: list[str] = []
        for info in await sdk.Sandbox.list():
            labels = getattr(info, "labels", {}) or {}
            if labels.get(label_key) == label_value:
                names.append(getattr(info, "name", "?"))
        return names
