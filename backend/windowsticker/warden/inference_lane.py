"""Inference lane: how an agent inside the microVM reaches the model without any key.

The guest talks plain HTTP to ``http://host.microsandbox.internal:<port>/lane/<token>/v1``.
This gateway, on the host:

* accepts only ``POST /chat/completions`` (and a one-model ``GET /models``) and only for the
  model the run was configured with; everything else is refused and logged;
* drops whatever Authorization the guest sent and adds the real key itself, so the guest
  never holds a key or a placeholder, and no TLS interception or DNS is needed;
* meters prompt and completion tokens from the upstream responses, so cost is measured on
  the host rather than reported by the agent, and refuses further calls once the run's token
  budget is spent.

Each run gets its own lane, identified by an unguessable token in the path.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from windowsticker.domain import EgressEvent

UPSTREAM = "https://api.vultrinference.com/v1"


@dataclass
class InferenceLaneState:
    run_id: str
    token: str
    model: str
    token_budget: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    events: list[EgressEvent] = field(default_factory=list)

    @property
    def spent(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _usage(obj: dict[str, Any]) -> tuple[int, int]:
    u = obj.get("usage") or {}
    pt = int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    ct = int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    return pt, ct


class InferenceGateway:
    def __init__(
        self,
        api_key: str,
        upstream: str = UPSTREAM,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key = api_key
        self._upstream = upstream.rstrip("/")
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(300, connect=15), transport=transport)
        self._lanes: dict[str, InferenceLaneState] = {}
        self.port = 0
        self._server: Any = None
        self._task: asyncio.Task[None] | None = None
        self.app = Starlette(
            routes=[
                Route("/lane/{token}/v1/chat/completions", self._chat, methods=["POST"]),
                Route("/lane/{token}/v1/models", self._models, methods=["GET"]),
                Route(
                    "/{rest:path}", self._refuse, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
                ),
            ]
        )

    # ------------------------------------------------------------------ lifecycle
    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        import socket

        import uvicorn

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        self.port = sock.getsockname()[1]
        config = uvicorn.Config(self.app, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve(sockets=[sock]))
        while not self._server.started:
            await asyncio.sleep(0.02)
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._task is not None:
            with contextlib.suppress(Exception):
                await self._task
        await self._http.aclose()

    def open(self, run_id: str, model: str, token_budget: int) -> InferenceLaneState:
        lane = InferenceLaneState(run_id, secrets.token_urlsafe(24), model, token_budget)
        self._lanes[lane.token] = lane
        return lane

    def close(self, token: str) -> InferenceLaneState:
        return self._lanes.pop(token)

    @staticmethod
    def base_url(lane: InferenceLaneState, port: int) -> str:
        return f"http://host.microsandbox.internal:{port}/lane/{lane.token}/v1"

    # ------------------------------------------------------------------ handlers
    def _log(self, lane: InferenceLaneState | None, allowed: bool, detail: str) -> None:
        if lane is not None:
            lane.events.append(
                EgressEvent(
                    host="inference-lane",
                    protocol="inference",
                    allowed=allowed,
                    detail=detail[:500],
                )
            )

    async def _refuse(self, request: Request) -> Response:
        path = request.url.path
        lane = None
        parts = path.split("/")
        if len(parts) > 2 and parts[1] == "lane":
            lane = self._lanes.get(parts[2])
        self._log(
            lane, False, f"{request.method} {path.split('/v1', 1)[-1] or path} refused: not allowed"
        )
        return JSONResponse(
            {"error": {"message": "not allowed by Window Sticker"}}, status_code=403
        )

    async def _models(self, request: Request) -> Response:
        lane = self._lanes.get(request.path_params["token"])
        if lane is None:
            return JSONResponse({"error": {"message": "unknown lane"}}, status_code=404)
        return JSONResponse({"object": "list", "data": [{"id": lane.model, "object": "model"}]})

    async def _chat(self, request: Request) -> Response:
        lane = self._lanes.get(request.path_params["token"])
        if lane is None:
            return JSONResponse({"error": {"message": "unknown lane"}}, status_code=404)
        try:
            body = json.loads(await request.body())
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._log(lane, False, "POST /chat/completions refused: body is not JSON")
            return JSONResponse({"error": {"message": "invalid JSON"}}, status_code=400)
        if body.get("model") != lane.model:
            self._log(lane, False, f"POST /chat/completions refused: model {body.get('model')!r}")
            return JSONResponse(
                {"error": {"message": f"only {lane.model} is allowed"}}, status_code=403
            )
        if lane.spent >= lane.token_budget:
            self._log(
                lane,
                False,
                f"POST /chat/completions refused: token budget {lane.token_budget} spent",
            )
            return JSONResponse({"error": {"message": "token budget exhausted"}}, status_code=429)

        lane.calls += 1
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        url = f"{self._upstream}/chat/completions"
        if body.get("stream"):
            body.setdefault("stream_options", {})["include_usage"] = True
            return StreamingResponse(
                self._stream(lane, url, headers, body), media_type="text/event-stream"
            )
        resp = await self._http.post(url, headers=headers, json=body)
        if resp.status_code < 400:
            pt, ct = _usage(resp.json())
            lane.prompt_tokens += pt
            lane.completion_tokens += ct
        self._log(lane, True, f"POST /chat/completions {lane.model} -> {resp.status_code}")
        return Response(resp.content, status_code=resp.status_code, media_type="application/json")

    async def _stream(
        self, lane: InferenceLaneState, url: str, headers: dict[str, str], body: dict[str, Any]
    ) -> AsyncIterator[bytes]:
        status = 0
        async with self._http.stream("POST", url, headers=headers, json=body) as resp:
            status = resp.status_code
            buffer = b""
            async for chunk in resp.aiter_bytes():
                yield chunk
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.startswith(b"data:") and b'"usage"' in line:
                        with contextlib.suppress(json.JSONDecodeError):
                            obj = json.loads(line[5:].strip())
                            if obj.get("usage"):
                                pt, ct = _usage(obj)
                                lane.prompt_tokens += pt
                                lane.completion_tokens += ct
        self._log(lane, True, f"POST /chat/completions {lane.model} (stream) -> {status}")
