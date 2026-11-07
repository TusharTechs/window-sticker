"""Reference agent: the brain stays outside the sandbox, only the hands go in.

The LLM loop runs on the runner host and talks to Vultr Serverless Inference. Every
tool call is checked by the agent's guardrails and then executed inside the run's
microVM. The sandbox therefore never holds an API key, and every action is recorded.

Non-shell tools (read_file, write_file, list_dir) are also recorded as command records
(``read_file /path``) so path-based tripwires apply to them uniformly.
"""

from __future__ import annotations

import base64
import json
import shlex
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from windowsticker.agents.config import AgentConfig
from windowsticker.agents.guardrails import GuardrailEngine
from windowsticker.agents.tools import TOOLS, truncate
from windowsticker.domain import CapEvent, CommandRecord, FinalReport, Step, ToolCall, utcnow
from windowsticker.inference.client import InferenceClient, InferenceError, Usage
from windowsticker.sandbox.base import Sandbox

EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _noop(_: str, __: dict[str, Any]) -> None:
    return None


@dataclass
class Attachment:
    path: str
    mime: str
    data: bytes


@dataclass
class AgentOutcome:
    steps: list[Step] = field(default_factory=list)
    commands: list[CommandRecord] = field(default_factory=list)
    written_paths: list[str] = field(default_factory=list)
    caps: list[CapEvent] = field(default_factory=list)
    final: FinalReport = field(default_factory=lambda: FinalReport(finished=False))
    usage: Usage = field(default_factory=Usage)
    model_turns: int = 0
    errors: list[str] = field(default_factory=list)


class ReferenceAgent:
    def __init__(
        self,
        config: AgentConfig,
        client: InferenceClient,
        sandbox: Sandbox,
        *,
        token_budget: int = 60_000,
        events: EventSink = _noop,
    ) -> None:
        self.config = config
        self.client = client
        self.sandbox = sandbox
        self.guardrails = GuardrailEngine(config.guardrails)
        self.token_budget = token_budget
        self.events = events
        self.outcome = AgentOutcome()

    def _messages(self, task: str, attachments: list[Attachment]) -> list[dict[str, Any]]:
        system = self.config.system_prompt + self.guardrails.system_prompt_suffix()
        user: Any = task
        if attachments:
            parts: list[dict[str, Any]] = [{"type": "text", "text": task}]
            for a in attachments:
                b64 = base64.b64encode(a.data).decode()
                parts.append({"type": "text", "text": f"Attachment: {a.path}"})
                parts.append(
                    {"type": "image_url", "image_url": {"url": f"data:{a.mime};base64,{b64}"}}
                )
            user = parts
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    async def run(self, task: str, attachments: list[Attachment] | None = None) -> AgentOutcome:
        messages = self._messages(task, attachments or [])
        out = self.outcome
        nudges = 0
        step_index = 0
        while True:
            if step_index >= self.config.max_steps:
                out.caps.append(CapEvent(kind="steps", detail=f"stopped after {step_index} steps"))
                break
            if out.usage.total_tokens >= self.token_budget:
                out.caps.append(
                    CapEvent(kind="tokens", detail=f"{out.usage.total_tokens} tokens used")
                )
                break
            extra = (
                {"reasoning_effort": self.config.reasoning_effort}
                if self.config.reasoning_effort
                else None
            )
            try:
                result = await self.client.chat(
                    self.config.model,
                    messages,
                    tools=TOOLS,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens_per_turn,
                    extra=extra,
                )
            except InferenceError as exc:
                out.errors.append(str(exc))
                await self.events("agent.error", {"error": str(exc)})
                break
            out.model_turns += 1
            out.usage.add(result.usage)

            if not result.tool_calls:
                # Models sometimes return prose, or nothing at all (for example when a turn
                # is spent on reasoning). Nudge twice before treating it as giving up.
                if nudges < 2:
                    if result.content.strip():
                        messages.append({"role": "assistant", "content": result.content})
                    messages.append(
                        {
                            "role": "user",
                            "content": "Continue with the tools, or call `finish` when done.",
                        }
                    )
                    nudges += 1
                    continue
                out.final = FinalReport(
                    finished=False, claimed_success=None, summary=result.content
                )
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": result.content or None,
                    "tool_calls": result.tool_calls,
                }
            )
            per_call_usage = Usage(
                result.usage.prompt_tokens // len(result.tool_calls),
                result.usage.completion_tokens // len(result.tool_calls),
                result.usage.cost_usd / len(result.tool_calls),
            )
            done = False
            for i, call in enumerate(result.tool_calls):
                step_index += 1
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("arguments must be an object")
                except (json.JSONDecodeError, ValueError) as exc:
                    args, parse_error = {}, str(exc)
                else:
                    parse_error = ""
                step = Step(
                    index=step_index,
                    thought=result.content if i == 0 else "",
                    tool_call=ToolCall(name=name, arguments=args),
                    prompt_tokens=per_call_usage.prompt_tokens,
                    completion_tokens=per_call_usage.completion_tokens,
                    cost_usd=per_call_usage.cost_usd,
                )
                await self.events("agent.step.start", {"step": step.model_dump(mode="json")})
                if parse_error:
                    tool_result = f"error: could not parse arguments: {parse_error}"
                elif name == "finish":
                    out.final = FinalReport(
                        finished=True,
                        claimed_success=bool(args.get("success")),
                        summary=str(args.get("summary", "")),
                    )
                    tool_result = "ok"
                    done = True
                else:
                    tool_result = await self._execute(step_index, name, args, step)
                step.tool_result = tool_result
                step.finished_at = utcnow()
                out.steps.append(step)
                await self.events("agent.step", {"step": step.model_dump(mode="json")})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", f"call_{step_index}"),
                        "content": tool_result,
                    }
                )
                if done:
                    break
            if done:
                break
        return out

    async def _execute(self, step_index: int, name: str, args: dict[str, Any], step: Step) -> str:
        out = self.outcome
        if name in ("read_file", "write_file", "list_dir"):
            path = str(args.get("path", "") or "/workspace")
            args["path"] = path if path.startswith("/") else "/workspace/" + path
        decision = self.guardrails.check(name, args)
        record_cmd = self._as_command(name, args)
        if not decision.allowed:
            step.blocked_by = decision.guardrail
            out.commands.append(
                CommandRecord(
                    step=step_index,
                    command=record_cmd,
                    exit_code=None,
                    blocked_by=decision.guardrail,
                )
            )
            await self.events(
                "guardrail.refused", {"step": step_index, "guardrail": decision.guardrail}
            )
            return f"refused by guardrail {decision.guardrail}: {decision.reason}"

        started = time.perf_counter()
        if name == "run_shell":
            timeout = min(float(args.get("timeout_s") or 60), 120.0)
            res = await self.sandbox.exec(
                str(args.get("command", "")), timeout_s=timeout, cwd="/workspace"
            )
            out.commands.append(
                CommandRecord(
                    step=step_index,
                    command=record_cmd,
                    exit_code=res.exit_code,
                    stdout=truncate(res.stdout, 20000),
                    stderr=truncate(res.stderr, 8000),
                    duration_s=res.duration_s,
                    timed_out=res.timed_out,
                )
            )
            if res.timed_out:
                out.caps.append(
                    CapEvent(
                        kind="exec_timeout", detail=f"step {step_index} exceeded {timeout:.0f}s"
                    )
                )
                return f"error: command timed out after {timeout:.0f}s and was killed"
            text = res.stdout + (f"\n[stderr]\n{res.stderr}" if res.stderr.strip() else "")
            return truncate(f"exit code {res.exit_code}\n{text}")

        if name == "read_file":
            path = str(args.get("path", ""))
            res = await self.sandbox.exec(f"cat -- {shlex.quote(path)}", timeout_s=20)
            out.commands.append(
                CommandRecord(
                    step=step_index,
                    command=record_cmd,
                    exit_code=res.exit_code,
                    stdout=truncate(res.stdout, 20000),
                    stderr=res.stderr[:2000],
                    duration_s=time.perf_counter() - started,
                )
            )
            return truncate(res.stdout if res.exit_code == 0 else f"error: {res.stderr.strip()}")

        if name == "write_file":
            path = str(args.get("path", ""))
            content = str(args.get("content", ""))
            await self.sandbox.write_file(path, content.encode())
            out.written_paths.append(path)
            out.commands.append(
                CommandRecord(
                    step=step_index,
                    command=record_cmd,
                    exit_code=0,
                    duration_s=time.perf_counter() - started,
                )
            )
            return f"wrote {len(content)} characters to {path}"

        if name == "list_dir":
            path = str(args.get("path", "/workspace"))
            res = await self.sandbox.exec(
                f"find {shlex.quote(path)} -maxdepth 4 -not -path '*/.git/*' | head -200",
                timeout_s=20,
            )
            out.commands.append(
                CommandRecord(
                    step=step_index,
                    command=record_cmd,
                    exit_code=res.exit_code,
                    stdout=truncate(res.stdout, 8000),
                    duration_s=res.duration_s,
                )
            )
            return truncate(res.stdout or res.stderr)

        return f"error: unknown tool {name}"

    @staticmethod
    def _as_command(name: str, args: dict[str, Any]) -> str:
        if name == "run_shell":
            return str(args.get("command", ""))
        if name in ("read_file", "write_file", "list_dir"):
            return f"{name} {args.get('path', '')}"
        return name
