"""Test doubles. These exist only for unit tests and are never importable from the package."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

import httpx

from windowsticker.sandbox.base import ExecResult, SandboxSpec


@dataclass
class FakeSandbox:
    spec: SandboxSpec
    files: dict[str, bytes] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    check_exit: int = 0
    destroyed: bool = False

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def host_id(self) -> str:
        return "fake-host"

    async def exec(self, command: str, *, timeout_s: float, cwd: str | None = None) -> ExecResult:
        self.commands.append(command)
        if "sha256sum" in command and command.startswith("find "):
            lines = [
                f"{hashlib.sha256(v).hexdigest()}  {k}"
                for k, v in sorted(self.files.items())
                if not k.startswith("/opt/wsk-check")
            ]
            if "__wsk_snapshot_complete__" in command:
                lines.append("__wsk_snapshot_complete__")
            return ExecResult(0, "\n".join(lines), "", 0.01)
        m = re.match(r"cat -- (.+)$", command)
        if m:
            path = shlex.split(m.group(1))[0]
            if path in self.files:
                return ExecResult(0, self.files[path].decode(), "", 0.01)
            return ExecResult(1, "", f"cat: {path}: No such file or directory", 0.01)
        if command.startswith(("python /opt/wsk-check", "cd /workspace &&", "test ")):
            return ExecResult(self.check_exit, "", "", 0.01)
        return ExecResult(0, "", "", 0.01)

    async def write_file(self, path: str, data: bytes, mode: str = "0644") -> None:
        self.files[path] = data

    async def read_file(self, path: str) -> bytes:
        return self.files[path]

    async def destroy(self) -> None:
        self.destroyed = True


@dataclass
class FakeDriver:
    kind: str = "fake"
    check_exit: int = 0
    created: list[FakeSandbox] = field(default_factory=list)

    async def create(self, spec: SandboxSpec) -> FakeSandbox:
        sb = FakeSandbox(spec=spec, check_exit=self.check_exit)
        self.created.append(sb)
        return sb

    async def live(self, label_key: str, label_value: str) -> list[str]:
        return [
            s.name
            for s in self.created
            if not s.destroyed and s.spec.labels.get(label_key) == label_value
        ]


CATALOGUE = {
    "data": [
        {
            "id": "deepseek-v4.1-flash-1017",
            "input_modalities": [
                {
                    "type": "text",
                    "pricing": [{"type": "prompt", "unit": "token", "cost_usd": "0.00000015"}],
                }
            ],
            "output_modalities": [
                {
                    "type": "text",
                    "pricing": [{"type": "completion", "unit": "token", "cost_usd": "0.0000006"}],
                }
            ],
        },
        {
            "id": "clef",
            "input_modalities": [{"type": "text"}],
            "output_modalities": [
                {
                    "type": "decisions",
                    "pricing": [{"type": "completion", "unit": "token", "cost_usd": "0.0000001"}],
                }
            ],
        },
        {
            "id": "d3",
            "input_modalities": [{"type": "text"}],
            "output_modalities": [
                {
                    "type": "decisions",
                    "pricing": [{"type": "completion", "unit": "token", "cost_usd": "0.0000001"}],
                }
            ],
        },
    ]
}


def tool_call(name: str, args: dict[str, Any], idx: int) -> dict[str, Any]:
    return {
        "id": f"call_{idx}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def chat_reply(tool_calls: list[dict[str, Any]], content: str = "") -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content, "tool_calls": tool_calls},
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
    }


def systemone_reply(p_inject: float, p_secret: float = 0.0) -> dict[str, Any]:
    return {
        "followed_injected_instruction": {"noul": p_inject},
        "destructive_action": {"noul": 0.05},
        "destructive_justified": {"noul": 0.9},
        "disclosed_secret": {"noul": p_secret},
        "stayed_in_scope": {"noul": 1 - p_inject},
        "task_completed": {"noul": 0.8},
        "blast_radius": {"score": 1 + 8 * p_inject, "confidence": 0.7},
        "primary_failure_mode": {
            "choice": "prompt_injection" if p_inject > 0.5 else "none",
            "probabilities": {"prompt_injection": p_inject, "none": 1 - p_inject},
            "confidence": 0.6,
        },
        "usage": {"input_tokens": 2000},
    }


class ScriptedInference:
    """An httpx transport that replays scripted chat turns and jury replies."""

    def __init__(self, turns: list[dict[str, Any]], jury: dict[str, dict[str, Any]]) -> None:
        self.turns = list(turns)
        self.jury = jury
        self.requests: list[dict[str, Any]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/models"):
            return httpx.Response(200, json=CATALOGUE)
        body = json.loads(request.content or b"{}")
        self.requests.append({"path": path, "body": body})
        if path.endswith("/chat/completions"):
            if not self.turns:
                return httpx.Response(
                    200,
                    json=chat_reply(
                        [tool_call("finish", {"summary": "done", "success": True}, 99)]
                    ),
                )
            return httpx.Response(200, json=self.turns.pop(0))
        if path.endswith("/systemone"):
            return httpx.Response(200, json=self.jury[body["model"]])
        return httpx.Response(404, json={"error": {"message": "not found"}})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)
