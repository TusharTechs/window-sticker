"""Egress Warden: the only door out of a sandbox.

Every sandbox's network policy denies all egress except one TCP port on the host. That
port is a lane of this proxy, opened for exactly one run. The warden:

* logs every connection attempt (CONNECT target, or plain-HTTP request line and a body
  sample) as an ``EgressEvent`` — this log is the evidence for network tripwires (traffic that bypasses the proxy cannot
  leave the deny-all guest, and bypassing it is itself flagged);
* allows only hosts on the lane's allowlist and refuses everything else with 403;
* never forwards to link-local / metadata / private addresses, even if allowlisted by
  mistake, because names are resolved and checked here, on the host.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import socket
from dataclasses import dataclass, field

from windowsticker.domain import EgressEvent
from windowsticker.warden.dns import DnsLane, system_upstream

BODY_SAMPLE = 2048
READ_LIMIT = 64 * 1024
CONNECT_TIMEOUT = 10.0


def _forbidden_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return bool(
        addr.is_link_local
        or addr.is_loopback
        or addr.is_private
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def host_allowed(host: str, allowlist: tuple[str, ...]) -> bool:
    host = host.lower().rstrip(".")
    for pattern in allowlist:
        p = pattern.lower().rstrip(".")
        if p.startswith("*.") and (host.endswith(p[1:]) or host == p[2:]):
            return True
        if host == p:
            return True
    return False


@dataclass
class Lane:
    run_id: str
    allowlist: tuple[str, ...]
    port: int = 0
    events: list[EgressEvent] = field(default_factory=list)
    server: asyncio.base_events.Server | None = None
    bytes_out: int = 0
    bytes_in: int = 0
    dns_allow: tuple[str, ...] = ()
    dns_port: int = 0
    dns_transport: asyncio.DatagramTransport | None = None


class EgressWarden:
    def __init__(
        self, bind_host: str = "127.0.0.1", advertise_host: str = "host.microsandbox.internal"
    ) -> None:
        # Microsandbox relays guest traffic for host.microsandbox.internal to the host's
        # loopback, so the warden never needs to listen on a public interface.
        self._dns_upstream: tuple[str, int] | None = None
        self._bind = bind_host
        self.advertise_host = advertise_host
        self._lanes: dict[str, Lane] = {}

    async def open_lane(
        self, run_id: str, allowlist: tuple[str, ...], dns_allow: tuple[str, ...] = ()
    ) -> Lane:
        """Open a proxy lane; with ``dns_allow``, also a filtering resolver for those names."""
        lane = Lane(run_id=run_id, allowlist=allowlist, dns_allow=dns_allow)

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await self._handle(lane, reader, writer)

        lane.server = await asyncio.start_server(handler, self._bind, 0, limit=READ_LIMIT)
        lane.port = lane.server.sockets[0].getsockname()[1]
        if dns_allow:
            loop = asyncio.get_running_loop()
            upstream = self._dns_upstream or system_upstream()
            transport, _ = await loop.create_datagram_endpoint(
                lambda: DnsLane(lambda n: host_allowed(n, dns_allow), lane.events, upstream),
                local_addr=("127.0.0.1", 0),
            )
            lane.dns_transport = transport
            lane.dns_port = transport.get_extra_info("sockname")[1]
        self._lanes[run_id] = lane
        return lane

    async def close_lane(self, run_id: str) -> Lane:
        lane = self._lanes.pop(run_id)
        if lane.dns_transport is not None:
            lane.dns_transport.close()
        if lane.server is not None:
            lane.server.close()
            with contextlib.suppress(Exception):
                await lane.server.wait_closed()
        return lane

    def address(self, lane: Lane) -> str:
        return f"{self.advertise_host}:{lane.port}"

    # ------------------------------------------------------------------ handling
    async def _handle(
        self, lane: Lane, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=15)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
            writer.close()
            return
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, target, _ = lines[0].split(" ", 2)
        except ValueError:
            await self._refuse(writer, 400)
            return
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        if method.upper() == "CONNECT":
            host, _, port_s = target.rpartition(":")
            port = int(port_s) if port_s.isdigit() else 443
            await self._tunnel(lane, host.strip("[]"), port, reader, writer, f"CONNECT {target}")
            return

        # Absolute-URI requests. Most clients send plain HTTP this way; some (busybox
        # wget) also send HTTPS this way instead of CONNECT. Both are logged.
        lower = target.lower()
        if lower.startswith("http://"):
            scheme, rest, default_port = "http", target[7:], 80
        elif lower.startswith("https://"):
            scheme, rest, default_port = "https", target[8:], 443
        else:
            lane.events.append(
                EgressEvent(
                    host=headers.get("host", "?"),
                    protocol="http",
                    allowed=False,
                    detail=f"malformed: {lines[0][:200]}",
                )
            )
            await self._refuse(writer, 400)
            return
        hostport, _, path = rest.partition("/")
        host, _, port_s = hostport.partition(":")
        port = int(port_s) if port_s.isdigit() else default_port
        body = b""
        length = int(headers.get("content-length", "0") or 0)
        if length:
            with contextlib.suppress(Exception):
                body = await asyncio.wait_for(reader.readexactly(min(length, BODY_SAMPLE)), 5)
        detail = f"{method} {target} {body[:BODY_SAMPLE].decode('utf-8', 'replace')}".strip()
        addr = await self._permitted(lane, host, port)
        allowed = addr is not None
        lane.events.append(
            EgressEvent(
                host=host, port=port, protocol=scheme, allowed=allowed, detail=detail[:4096]
            )
        )
        if addr is None or scheme == "https":
            # We never originate TLS on the agent's behalf; HTTPS must use CONNECT.
            await self._refuse(writer, 403)
            return
        # Forward the original request (with path rewritten to origin-form).
        origin_line = f"{method} /{path} HTTP/1.1\r\n".encode()
        rebuilt = (
            origin_line
            + b"\r\n".join(line.encode("latin-1") for line in lines[1:] if line)
            + b"\r\n\r\n"
            + body
        )
        await self._forward(lane, addr, port, rebuilt, reader, writer)

    async def _permitted(self, lane: Lane, host: str, port: int) -> str | None:
        """The checked address to connect to, or None. Connecting to the address that was
        checked (not re-resolving the name) closes the DNS-rebinding window."""
        if not host_allowed(host, lane.allowlist):
            return None
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        except OSError:
            return None
        addrs = [str(info[4][0]) for info in infos]
        if not addrs or any(_forbidden_ip(a) for a in addrs):
            return None
        return addrs[0]

    async def _tunnel(
        self,
        lane: Lane,
        host: str,
        port: int,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        detail: str,
    ) -> None:
        addr = await self._permitted(lane, host, port)
        lane.events.append(
            EgressEvent(
                host=host, port=port, protocol="https", allowed=addr is not None, detail=detail
            )
        )
        if addr is None:
            await self._refuse(writer, 403)
            return
        try:
            up_r, up_w = await asyncio.wait_for(
                asyncio.open_connection(addr, port), CONNECT_TIMEOUT
            )
        except (OSError, TimeoutError):
            await self._refuse(writer, 502)
            return
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await self._pipe(lane, reader, writer, up_r, up_w)

    async def _forward(
        self,
        lane: Lane,
        host: str,
        port: int,
        first: bytes,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            up_r, up_w = await asyncio.wait_for(
                asyncio.open_connection(host, port), CONNECT_TIMEOUT
            )
        except (OSError, TimeoutError):
            await self._refuse(writer, 502)
            return
        up_w.write(first)
        await up_w.drain()
        await self._pipe(lane, reader, writer, up_r, up_w)

    async def _pipe(
        self,
        lane: Lane,
        c_r: asyncio.StreamReader,
        c_w: asyncio.StreamWriter,
        u_r: asyncio.StreamReader,
        u_w: asyncio.StreamWriter,
    ) -> None:
        async def copy(
            src: asyncio.StreamReader, dst: asyncio.StreamWriter, outbound: bool
        ) -> None:
            try:
                while chunk := await src.read(65536):
                    if outbound:
                        lane.bytes_out += len(chunk)
                    else:
                        lane.bytes_in += len(chunk)
                    dst.write(chunk)
                    await dst.drain()
            except (ConnectionError, asyncio.CancelledError):
                pass
            finally:
                with contextlib.suppress(Exception):
                    dst.close()

        await asyncio.gather(copy(c_r, u_w, True), copy(u_r, c_w, False))

    @staticmethod
    async def _refuse(writer: asyncio.StreamWriter, status: int) -> None:
        reason = {400: "Bad Request", 403: "Forbidden by Window Sticker", 502: "Bad Gateway"}[
            status
        ]
        body = f"{status} {reason}\n".encode()
        writer.write(
            f"HTTP/1.1 {status} {reason}\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        with contextlib.suppress(Exception):
            await writer.drain()
            writer.close()
