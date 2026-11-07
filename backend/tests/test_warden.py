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
