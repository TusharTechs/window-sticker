"""Warden DNS lane: the only resolver a sandbox can use when it is allowed DNS at all.

Plain DNS forwarding is an exfiltration channel: data can ride in query names
(``<secret>.attacker.example``) to whoever runs the authoritative server. This resolver
answers only allowlisted names (by forwarding to the host's upstream resolver) and answers
NXDOMAIN to everything else without forwarding it. Every query is logged against the run,
so a DNS exfiltration attempt becomes evidence instead of a silent leak.
"""

from __future__ import annotations

import asyncio
import contextlib
import struct
from collections.abc import Callable

from windowsticker.domain import EgressEvent


def parse_qname(packet: bytes) -> str | None:
    """Return the question's name, or None for a malformed packet or one that asks more
    than one question (a second question could otherwise ride past the allowlist check)."""
    if len(packet) < 12 or struct.unpack(">H", packet[4:6])[0] != 1:
        return None
    labels: list[str] = []
    i = 12
    while i < len(packet):
        n = packet[i]
        if n == 0:
            return ".".join(labels).lower()
        if n & 0xC0:  # compression is not used in questions we accept
            return None
        i += 1
        labels.append(packet[i : i + n].decode("ascii", "replace"))
        i += n
    return None


def nxdomain(query: bytes) -> bytes:
    """Build an NXDOMAIN reply that echoes the question."""
    if len(query) < 12:
        return b""
    qid = query[:2]
    rd = query[2] & 0x01
    flags = struct.pack(">BB", 0x80 | rd, 0x80 | 0x03)  # QR, RD copied, RA, RCODE=3
    counts = struct.pack(">HHHH", 1, 0, 0, 0)
    return qid + flags + counts + query[12:]


class _Relay(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if not self.future.done():
            self.future.set_result(data)


async def forward(packet: bytes, upstream: tuple[str, int], timeout: float = 3.0) -> bytes | None:
    loop = asyncio.get_running_loop()
    transport, proto = await loop.create_datagram_endpoint(_Relay, remote_addr=upstream)
    try:
        transport.sendto(packet)
        return await asyncio.wait_for(proto.future, timeout)
    except TimeoutError:
        return None
    finally:
        transport.close()


class DnsLane(asyncio.DatagramProtocol):
    def __init__(
        self,
        allowed: Callable[[str], bool],
        log: list[EgressEvent],
        upstream: tuple[str, int],
    ) -> None:
        self.allowed = allowed
        self.log = log
        self.upstream = upstream
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        asyncio.get_running_loop().create_task(self._answer(data, addr))

    async def _answer(self, data: bytes, addr: tuple[str, int]) -> None:
        name = parse_qname(data)
        ok = bool(name) and self.allowed(name or "")
        self.log.append(
            EgressEvent(
                host=name or "?", port=53, protocol="dns", allowed=ok, detail=f"DNS query {name}"
            )
        )
        reply = await forward(data, self.upstream) if ok else None
        if reply is None:
            reply = nxdomain(data)
        if self.transport is not None and reply:
            with contextlib.suppress(Exception):
                self.transport.sendto(reply, addr)


def system_upstream() -> tuple[str, int]:
    """First nameserver from the host's resolv.conf, falling back to a public resolver."""
    for path in ("/run/systemd/resolve/resolv.conf", "/etc/resolv.conf"):
        try:
            with open(path) as fh:
                for line in fh:
                    parts = line.split()
                    if (
                        len(parts) >= 2
                        and parts[0] == "nameserver"
                        and not parts[1].startswith("127.")
                    ):
                        return parts[1], 53
        except OSError:
            continue
    return "1.1.1.1", 53
