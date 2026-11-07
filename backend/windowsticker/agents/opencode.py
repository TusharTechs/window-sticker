"""OpenCode adapter: a real, widely used coding agent running *inside* the microVM.

Unlike the reference agent, OpenCode's brain runs in the sandbox, so it needs to reach the
model. It does so with a placeholder key: the guest's VULTR_INFERENCE_API_KEY is a
Microsandbox placeholder that the runtime's TLS proxy replaces with the real key only on
requests to api.vultrinference.com. Every other destination goes through the warden.

OpenCode is driven headless (``opencode run --format json --auto``) and its JSON event
stream is converted into the same Steps and CommandRecords the graders already understand.
"""

from __future__ import annotations

import json
import shlex
from datetime import UTC, datetime
from typing import Any

from windowsticker.agents.config import AgentConfig
from windowsticker.agents.reference import AgentOutcome, Attachment, EventSink, _noop
from windowsticker.domain import CapEvent, CommandRecord, FinalReport, Step, ToolCall
from windowsticker.inference.client import InferenceClient, Usage
from windowsticker.sandbox.base import Sandbox

OUTPUT = "/tmp/wsk-opencode.jsonl"
STDERR = "/tmp/wsk-opencode.err"
INFERENCE_HOST = "api.vultrinference.com"

# OpenCode tool name -> how we record it for path- and command-based tripwires.
PATH_TOOLS = {"read": "read_file", "write": "write_file", "edit": "write_file", "list": "list_dir"}


def _ts(ms: Any) -> datetime:
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


def command_line(agent: AgentConfig, task: str, attachments: list[Attachment]) -> str:
    # The task must come before any -f: -f takes a list, and anything after it (including
    # the task) would be read as more file paths.
    parts = ["opencode", "run", "--format", "json", "--auto", "-m", f"vultr/{agent.model}", task]
    for a in attachments:
        parts += ["-f", a.path]
    quoted = " ".join(shlex.quote(p) for p in parts)
    return f"cd /workspace && {quoted} > {OUTPUT} 2> {STDERR}"


def parse_events(
    lines: list[str],
) -> tuple[list[Step], list[CommandRecord], list[str], str, int, int]:
    """Convert OpenCode's JSON events into steps and command records.

    Returns steps, commands, written paths, final text, prompt tokens, completion tokens.
    """
    steps: list[Step] = []
    commands: list[CommandRecord] = []
    written: list[str] = []
    texts: list[str] = []
    prompt_tokens = completion_tokens = 0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        part = event.get("part") or {}
        if kind == "tool_use":
            state = part.get("state") or {}
            tool = str(part.get("tool", ""))
            args = state.get("input") or {}
            index = len(steps) + 1
            output = str(state.get("output") or (state.get("metadata") or {}).get("output") or "")
            if tool == "bash":
                cmd = str(args.get("command", ""))
                exit_code = (state.get("metadata") or {}).get("exit")
            elif tool in PATH_TOOLS:
                path = str(args.get("filePath") or args.get("path") or "")
                cmd = f"{PATH_TOOLS[tool]} {path}"
                exit_code = 0 if state.get("status") == "completed" else None
                if PATH_TOOLS[tool] == "write_file" and path:
                    written.append(path)
            else:
                cmd = f"{tool} {json.dumps(args)[:400]}"
                exit_code = 0 if state.get("status") == "completed" else None
            started = (state.get("time") or {}).get("start")
            ended = (state.get("time") or {}).get("end")
            steps.append(
                Step(
                    index=index,
                    started_at=_ts(started),
                    finished_at=_ts(ended),
                    thought=" ".join(texts[-1:]) if texts else "",
                    tool_call=ToolCall(
                        name="run_shell" if tool == "bash" else tool, arguments=args
                    ),
                    tool_result=output[:6000],
                )
            )
            commands.append(
                CommandRecord(
                    step=index,
                    command=cmd,
                    exit_code=exit_code if isinstance(exit_code, int) else None,
                    stdout=output[:20000],
                )
            )
        elif kind == "text":
            text = str(part.get("text", "")).strip()
            if text:
                texts.append(text)
        elif kind == "step_finish":
            tokens = part.get("tokens") or {}
            cache = tokens.get("cache") or {}
            prompt_tokens += int(tokens.get("input") or 0) + int(cache.get("read") or 0)
            completion_tokens += int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0)
    final = texts[-1] if texts else ""
    return steps, commands, written, final, prompt_tokens, completion_tokens


class OpenCodeAgent:
    """Runs OpenCode headless in the sandbox and records what it did."""

    def __init__(
        self,
        config: AgentConfig,
        client: InferenceClient,
        sandbox: Sandbox,
        *,
        wall_clock_s: float = 240.0,
        events: EventSink = _noop,
    ) -> None:
        if config.guardrails:
            raise ValueError(
                "OpenCode brings its own safety behaviour; guardrails apply to the reference agent"
            )
        self.config = config
        self.client = client
        self.sandbox = sandbox
        self.wall_clock_s = wall_clock_s
        self.events = events
        self.outcome = AgentOutcome()

    async def run(self, task: str, attachments: list[Attachment] | None = None) -> AgentOutcome:
        out = self.outcome
        res = await self.sandbox.exec(
            command_line(self.config, task, attachments or []), timeout_s=self.wall_clock_s
        )
        if res.timed_out:
            out.caps.append(
                CapEvent(kind="wall_clock", detail=f"OpenCode exceeded {self.wall_clock_s:.0f}s")
            )
        raw = await self.sandbox.exec(f"cat {OUTPUT} 2>/dev/null", timeout_s=30)
        steps, commands, written, final, pt, ct = parse_events(raw.stdout.splitlines())
        if not steps and not final:
            err = await self.sandbox.exec(f"tail -c 2000 {STDERR} 2>/dev/null", timeout_s=15)
            out.errors.append(
                f"OpenCode produced no events (exit {res.exit_code}): {err.stdout.strip()[-400:]}"
            )
        out.usage = Usage(pt, ct, await self.client.cost(self.config.model, pt, ct))
        per_step = out.usage.cost_usd / max(1, len(steps))
        for s in steps:
            s.cost_usd = per_step
            await self.events("agent.step", {"step": s.model_dump(mode="json")})
        out.steps, out.commands, out.written_paths = steps, commands, written
        out.model_turns = len(steps)
        # OpenCode has no explicit success flag; the hidden check decides success, and a
        # finished run with a final message is recorded as finished.
        out.final = FinalReport(finished=bool(final), claimed_success=None, summary=final)
        return out
