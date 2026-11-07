"""Sandbox driver interface.

The harness never talks to a sandbox runtime directly. It asks a driver for a fresh
sandbox built from a spec, uses it, and destroys it. Drivers exist for Microsandbox
microVMs (production) and, later, for whole throwaway Vultr instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ExecResult:
    exit_code: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False


@dataclass(frozen=True)
class SecretSpec:
    """A credential the sandbox may *use* but never *see*.

    The guest receives a placeholder; the runtime's TLS proxy substitutes the real value
    only on requests to ``allow_hosts``. Any attempt to send the placeholder elsewhere is
    blocked and, by default, terminates the sandbox.
    """

    env: str
    value: str = field(repr=False)
    allow_hosts: tuple[str, ...]
    terminate_on_violation: bool = True


@dataclass(frozen=True)
class NetworkSpec:
    """Deny-by-default egress. Only the Egress Warden (and nothing else) is reachable."""

    warden_host: str | None = None  # host:port of the Egress Warden as seen from the guest
    allow_hosts: tuple[str, ...] = ()  # enforced by the warden
    allow_dns: bool = False
    block_metadata: bool = True
    # Destinations reached directly (not through the warden), e.g. the inference API for an
    # agent whose brain runs inside the VM. Each is host:port.
    direct: tuple[str, ...] = ()
    # host:port of the warden DNS lane on the host; required whenever direct is non-empty.
    dns_resolver: str | None = None


@dataclass(frozen=True)
class SandboxSpec:
    name: str
    image: str
    cpus: int = 1
    memory_mib: int = 1024
    network: NetworkSpec = field(default_factory=NetworkSpec)
    secrets: tuple[SecretSpec, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    max_duration_s: float | None = None  # hard VM lifetime, enforced by the runtime
    intercept_tls: bool = False  # required for placeholder-secret substitution


@runtime_checkable
class Sandbox(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def host_id(self) -> str:
        """Identifier of the physical host (for the Live Grid tile)."""
        ...

    async def exec(self, command: str, *, timeout_s: float, cwd: str | None = None) -> ExecResult:
        """Run ``command`` through ``/bin/sh -c`` inside the sandbox."""
        ...

    async def write_file(self, path: str, data: bytes, mode: str = "0644") -> None: ...

    async def read_file(self, path: str) -> bytes: ...

    async def destroy(self) -> None: ...


@runtime_checkable
class SandboxDriver(Protocol):
    kind: str

    async def create(self, spec: SandboxSpec) -> Sandbox: ...

    async def live(self, label_key: str, label_value: str) -> list[str]:
        """Names of sandboxes still alive with this label (used to prove teardown)."""
        ...
