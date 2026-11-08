import json

import httpx
import pytest

from windowsticker.warden.inference_lane import InferenceGateway

seen: list[httpx.Request] = []


def upstream(request: httpx.Request) -> httpx.Response:
    seen.append(request)
    body = json.loads(request.content)
    if body.get("stream"):
        sse = (
            b'data: {"choices":[{"delta":{"content":"hi"}}],"usage":null}\n\n'
            b'data: {"choices":[],"usage":{"prompt_tokens":120,"completion_tokens":7}}\n\n'
            b"data: [DONE]\n\n"
        )
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 5},
        },
    )


@pytest.fixture
def gw():
    seen.clear()
    return InferenceGateway(
        "REAL-KEY", "https://up.test/v1", transport=httpx.MockTransport(upstream)
    )


def client(gw):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=gw.app), base_url="http://lane")


async def test_key_is_added_on_the_host_and_guest_auth_dropped(gw):
    lane = gw.open("r1", "deepseek-v4.1-flash-1017", 10_000)
    async with client(gw) as c:
        r = await c.post(
            f"/lane/{lane.token}/v1/chat/completions",
            json={"model": "deepseek-v4.1-flash-1017", "messages": []},
            headers={"Authorization": "Bearer guest-placeholder"},
        )
    assert r.status_code == 200
    assert seen[0].headers["Authorization"] == "Bearer REAL-KEY"
    assert (lane.prompt_tokens, lane.completion_tokens, lane.calls) == (50, 5, 1)


async def test_streaming_usage_is_metered(gw):
    lane = gw.open("r1", "m", 10_000)
    async with client(gw) as c:
        r = await c.post(
            f"/lane/{lane.token}/v1/chat/completions",
            json={"model": "m", "stream": True, "messages": []},
        )
        assert b"[DONE]" in r.content
    assert json.loads(seen[0].content)["stream_options"] == {"include_usage": True}
    assert (lane.prompt_tokens, lane.completion_tokens) == (120, 7)


async def test_other_models_paths_and_lanes_are_refused_and_logged(gw):
    lane = gw.open("r1", "m", 10_000)
    async with client(gw) as c:
        assert (
            await c.post(f"/lane/{lane.token}/v1/chat/completions", json={"model": "glm-5.3"})
        ).status_code == 403
        assert (await c.post(f"/lane/{lane.token}/v1/files", json={})).status_code == 403
        assert (await c.post(f"/lane/{lane.token}/v1/vector_store", json={})).status_code == 403
        assert (
            await c.post("/lane/not-a-lane/v1/chat/completions", json={"model": "m"})
        ).status_code == 404
        models = (await c.get(f"/lane/{lane.token}/v1/models")).json()
    assert [m["id"] for m in models["data"]] == ["m"]
    assert seen == []  # nothing refused ever reached the upstream
    refused = [e for e in lane.events if not e.allowed]
    assert len(refused) == 3 and all(e.protocol == "inference" for e in refused)


async def test_token_budget_is_enforced(gw):
    lane = gw.open("r1", "m", 40)
    async with client(gw) as c:
        first = await c.post(
            f"/lane/{lane.token}/v1/chat/completions", json={"model": "m", "messages": []}
        )
        second = await c.post(
            f"/lane/{lane.token}/v1/chat/completions", json={"model": "m", "messages": []}
        )
    assert first.status_code == 200 and second.status_code == 429
    assert len(seen) == 1


async def test_gateway_serves_on_a_real_port():
    gw = InferenceGateway("K", "https://up.test/v1", transport=httpx.MockTransport(upstream))
    port = await gw.start()
    try:
        lane = gw.open("r", "m", 1000)
        async with httpx.AsyncClient() as c:
            r = await c.get(f"http://127.0.0.1:{port}/lane/{lane.token}/v1/models")
        assert r.status_code == 200
        assert InferenceGateway.base_url(lane, port).endswith(f":{port}/lane/{lane.token}/v1")
    finally:
        await gw.stop()


async def test_inside_agents_require_the_gateway():
    from tests.fakes import FakeDriver, ScriptedInference
    from windowsticker.agents.config import AgentConfig
    from windowsticker.inference.client import InferenceClient
    from windowsticker.runner.run import execute_run
    from windowsticker.traps import load_suite
    from windowsticker.warden.proxy import EgressWarden

    suite = load_suite("v1")
    async with InferenceClient("k", transport=ScriptedInference([], {}).transport()) as c:
        with pytest.raises(RuntimeError, match="inference gateway"):
            await execute_run(
                suite=suite,
                scenario=suite.get("readme-exfil"),
                agent=AgentConfig(name="oc", adapter="opencode"),
                driver=FakeDriver(),
                client=c,
                warden=EgressWarden(),
                image="python",
            )
