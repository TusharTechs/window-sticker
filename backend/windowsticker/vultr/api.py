"""Minimal async client for the Vultr platform API (v2).

Used for the sandbox-host lifecycle, firewall groups, tags and billing. Every
instance Window Sticker creates carries the ``window-sticker`` tag so it can be found
and torn down, and teardown can be proven.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

TAG = "window-sticker"


class VultrAPIError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status


class VultrAPI:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.vultr.com/v2",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "windowsticker/0.1"},
            timeout=httpx.Timeout(60.0, connect=15.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> VultrAPI:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(4):
            resp = await self._http.request(method, path, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                try:
                    message = resp.json().get("error", resp.text)
                except ValueError:
                    message = resp.text
                raise VultrAPIError(resp.status_code, str(message)[:400])
            if resp.status_code == 204 or not resp.content:
                return {}
            data: dict[str, Any] = resp.json()
            return data
        raise VultrAPIError(resp.status_code, "retries exhausted")

    async def _paged(self, path: str, key: str, **params: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cursor = ""
        while True:
            q = {"per_page": 500, **params}
            if cursor:
                q["cursor"] = cursor
            data = await self._call("GET", path, params=q)
            out += data.get(key, [])
            cursor = (data.get("meta", {}).get("links", {}) or {}).get("next", "")
            if not cursor:
                return out

    # ------------------------------------------------------------------ account
    async def balance(self) -> dict[str, Any]:
        """Only billing figures; identity fields are dropped on purpose."""
        acct = (await self._call("GET", "/account")).get("account", {})
        keep = ("balance", "pending_charges", "last_payment_date", "last_payment_amount")
        return {k: acct.get(k) for k in keep}

    # ------------------------------------------------------------------ catalogue
    async def regions(self) -> list[dict[str, Any]]:
        return await self._paged("/regions", "regions")

    async def plans(self, plan_type: str = "all") -> list[dict[str, Any]]:
        return await self._paged("/plans", "plans", type=plan_type)

    async def os_list(self) -> list[dict[str, Any]]:
        return await self._paged("/os", "os")

    # ------------------------------------------------------------------ ssh keys
    async def ssh_keys(self) -> list[dict[str, Any]]:
        return await self._paged("/ssh-keys", "ssh_keys")

    async def create_ssh_key(self, name: str, public_key: str) -> dict[str, Any]:
        data = await self._call("POST", "/ssh-keys", json={"name": name, "ssh_key": public_key})
        key: dict[str, Any] = data["ssh_key"]
        return key

    # ------------------------------------------------------------------ firewall
    async def create_firewall_group(self, description: str) -> str:
        data = await self._call("POST", "/firewalls", json={"description": description})
        return str(data["firewall_group"]["id"])

    async def add_firewall_rule(
        self,
        group_id: str,
        *,
        ip_type: str,
        protocol: str,
        port: str,
        subnet: str,
        subnet_size: int,
        notes: str = "",
    ) -> None:
        await self._call(
            "POST",
            f"/firewalls/{group_id}/rules",
            json={
                "ip_type": ip_type,
                "protocol": protocol,
                "port": port,
                "subnet": subnet,
                "subnet_size": subnet_size,
                "notes": notes,
            },
        )

    async def firewall_groups(self) -> list[dict[str, Any]]:
        return await self._paged("/firewalls", "firewall_groups")

    # ------------------------------------------------------------------ instances
    async def create_instance(self, **body: Any) -> dict[str, Any]:
        tags = list(dict.fromkeys([*body.pop("tags", []), TAG]))
        data = await self._call("POST", "/instances", json={**body, "tags": tags})
        inst: dict[str, Any] = data["instance"]
        return inst

    async def instance(self, instance_id: str) -> dict[str, Any]:
        inst: dict[str, Any] = (await self._call("GET", f"/instances/{instance_id}"))["instance"]
        return inst

    async def instances(self, tag: str | None = TAG) -> list[dict[str, Any]]:
        params = {"tag": tag} if tag else {}
        return await self._paged("/instances", "instances", **params)

    async def delete_instance(self, instance_id: str) -> None:
        await self._call("DELETE", f"/instances/{instance_id}")

    async def wait_active(self, instance_id: str, timeout_s: float = 600) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        while True:
            inst = await self.instance(instance_id)
            if inst.get("status") == "active" and inst.get("server_status") == "ok":
                return inst
            if loop.time() > deadline:
                raise TimeoutError(f"instance {instance_id} not ready: {inst.get('status')}")
            await asyncio.sleep(5)
