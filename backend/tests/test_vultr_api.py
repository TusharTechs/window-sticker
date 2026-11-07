import json

import httpx

from windowsticker.vultr.api import TAG, VultrAPI


async def test_create_instance_always_carries_the_tag():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(202, json={"instance": {"id": "i-1", "status": "pending"}})

    async with VultrAPI("k", transport=httpx.MockTransport(handler)) as api:
        await api.create_instance(
            region="atl", plan="vx1-g-4c-16g-240s", os_id=2284, tags=["sandbox-host"]
        )
    assert seen["body"]["tags"] == ["sandbox-host", TAG]


async def test_balance_drops_identity_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "account": {
                    "name": "someone",
                    "email": "x@example.com",
                    "balance": -200,
                    "pending_charges": 1.5,
                }
            },
        )

    async with VultrAPI("k", transport=httpx.MockTransport(handler)) as api:
        b = await api.balance()
    assert "email" not in b and "name" not in b and b["balance"] == -200


async def test_paging_follows_cursor():
    pages = {
        "": {"instances": [{"id": "a"}], "meta": {"links": {"next": "c2"}}},
        "c2": {"instances": [{"id": "b"}], "meta": {"links": {"next": ""}}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[request.url.params.get("cursor", "")])

    async with VultrAPI("k", transport=httpx.MockTransport(handler)) as api:
        ids = [i["id"] for i in await api.instances()]
    assert ids == ["a", "b"]
