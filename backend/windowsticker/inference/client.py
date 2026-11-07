"""Async client for Vultr Serverless Inference (OpenAI-compatible chat + System One).

Retries follow the documented behaviour: honour ``Retry-After`` on 429, back off on
502/503/504/529, and keep timeouts generous because requests over the per-model
concurrency limit queue server-side for up to two minutes.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from windowsticker.inference.pricing import ModelPrice, parse_catalogue

RETRY_STATUSES = {429, 502, 503, 504, 529}


class InferenceError(RuntimeError):
    def __init__(self, status: int, message: str, body: Any = None) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status
        self.body = body


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: Usage) -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cost_usd += other.cost_usd

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResult:
    model: str
    content: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str | None
    usage: Usage
    latency_s: float
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


class InferenceClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.vultrinference.com/v1",
        *,
        timeout_s: float = 240.0,
        max_retries: int = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "windowsticker/0.1"},
            timeout=httpx.Timeout(timeout_s, connect=15.0),
            transport=transport,
        )
        self._max_retries = max_retries
        self._api_key = api_key
        self._prices: dict[str, ModelPrice] | None = None
        self._price_lock = asyncio.Lock()

    def secret_for_sandbox(self) -> str:
        """The key, for a Microsandbox placeholder secret. It never enters the guest."""
        return self._api_key

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> InferenceClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ------------------------------------------------------------------ transport
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        attempt = 0
        while True:
            resp = await self._http.request(method, path, **kwargs)
            if resp.status_code < 400:
                data: dict[str, Any] = resp.json()
                return data
            if resp.status_code in RETRY_STATUSES and attempt < self._max_retries:
                attempt += 1
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else min(2**attempt, 30) + random.random()
                await asyncio.sleep(delay)
                continue
            try:
                body = resp.json()
                message = body.get("error", {}).get("message") or resp.text
            except ValueError:
                body, message = None, resp.text
            raise InferenceError(resp.status_code, str(message)[:500], body)

    # ------------------------------------------------------------------ catalogue
    async def models(self) -> dict[str, Any]:
        return await self._request("GET", "/models")

    async def prices(self) -> dict[str, ModelPrice]:
        async with self._price_lock:
            if self._prices is None:
                self._prices = parse_catalogue(await self.models())
            return self._prices

    async def cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        price = (await self.prices()).get(model)
        return price.cost(prompt_tokens, completion_tokens) if price else 0.0

    # ------------------------------------------------------------------ chat
    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if seed is not None:
            body["seed"] = seed
        if extra:
            body.update(extra)
        started = time.perf_counter()
        data = await self._request("POST", "/chat/completions", json=body)
        latency = time.perf_counter() - started
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage_raw = data.get("usage") or {}
        pt = int(usage_raw.get("prompt_tokens") or usage_raw.get("input_tokens") or 0)
        ct = int(usage_raw.get("completion_tokens") or usage_raw.get("output_tokens") or 0)
        usage = Usage(pt, ct, await self.cost(model, pt, ct))
        return ChatResult(
            model=model,
            content=message.get("content") or "",
            tool_calls=list(message.get("tool_calls") or []),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            latency_s=latency,
            raw=data,
        )

    # ------------------------------------------------------------------ System One
    async def decide(
        self,
        model: str,
        state: Any,
        questions: dict[str, dict[str, Any]],
        *,
        assets: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], Usage]:
        body: dict[str, Any] = {"model": model, "state": state, "questions": questions}
        headers = {}
        if assets:
            body["assets"] = assets
            headers["TypeSafe-Danger-Zone-Images"] = "true"
        data = await self._request("POST", "/systemone", json=body, headers=headers)
        usage_raw = data.get("usage") or {}
        pt = int(usage_raw.get("input_tokens") or usage_raw.get("prompt_tokens") or 0)
        ct = int(usage_raw.get("output_tokens") or usage_raw.get("completion_tokens") or 0)
        return data, Usage(pt, ct, await self.cost(model, pt, ct))

    # ------------------------------------------------------------------ moderation
    async def moderate(self, text: str, model: str = "nemotron-3.5-content-safety") -> ChatResult:
        return await self.chat(model, [{"role": "user", "content": text}], max_tokens=64)
