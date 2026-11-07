import httpx
import pytest

from tests.fakes import CATALOGUE
from windowsticker.inference.client import InferenceClient, InferenceError
from windowsticker.inference.pricing import parse_catalogue


def test_prices_read_from_input_and_output_modalities():
    prices = parse_catalogue(CATALOGUE)
    ds = prices["deepseek-v4.1-flash-1017"]
    assert ds.input_per_token == pytest.approx(0.15e-6)
    assert ds.output_per_token == pytest.approx(0.6e-6)
    assert ds.cost(1_000_000, 1_000_000) == pytest.approx(0.75)
    clef = prices["clef"]
    assert clef.input_per_token == clef.output_per_token == pytest.approx(0.1e-6)


async def test_client_retries_429_using_retry_after():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=CATALOGUE)
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429, headers={"Retry-After": "0"}, json={"error": {"message": "slow down"}}
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    async with InferenceClient("k", transport=httpx.MockTransport(handler)) as c:
        res = await c.chat("deepseek-v4.1-flash-1017", [{"role": "user", "content": "x"}])
    assert res.content == "hi" and calls["n"] == 2
    assert res.usage.cost_usd == pytest.approx(10 * 0.15e-6 + 5 * 0.6e-6)


async def test_client_raises_on_client_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    async with InferenceClient("k", transport=httpx.MockTransport(handler), max_retries=0) as c:
        with pytest.raises(InferenceError) as info:
            await c.chat("m", [])
    assert info.value.status == 401


async def test_systemone_sends_image_header_only_with_assets():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json=CATALOGUE)
        seen["header"] = request.headers.get("TypeSafe-Danger-Zone-Images")
        return httpx.Response(200, json={"q": {"noul": 0.5}})

    async with InferenceClient("k", transport=httpx.MockTransport(handler)) as c:
        await c.decide("clef", "s", {"q": {"type": "noul", "instructions": "?"}})
        assert seen["header"] is None
        await c.decide(
            "clef", "s img1", {"q": {"type": "noul", "instructions": "?"}}, assets={"img1": "AAAA"}
        )
        assert seen["header"] == "true"
