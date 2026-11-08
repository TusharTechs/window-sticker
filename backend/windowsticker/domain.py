"""Core records shared by the agent harness, the graders and the statistics.

Everything a run produces is captured here as plain data, so a run can be stored,
replayed in the UI, re-graded later, and audited by a third party.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1}[self.value]

    def at_least(self, other: Severity) -> bool:
        return self.rank >= other.rank


class CommandRecord(BaseModel):
    """One command the agent caused to run inside the sandbox."""

    step: int
    command: str
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_s: float = 0.0
    timed_out: bool = False
    blocked_by: str | None = None  # guardrail that refused to run it, if any


class EgressEvent(BaseModel):
    """One outbound connection attempt seen by the Egress Warden or the sandbox runtime."""

    at: datetime = Field(default_factory=utcnow)
    host: str
    port: int | None = None
    protocol: str = "tcp"  # tcp | http | https | dns
    allowed: bool
    detail: str = ""  # request line, SNI, query name or payload sample (truncated)
    source: str = "warden"  # warden | runtime


class CapEvent(BaseModel):
    """A resource or budget limit that fired."""

    kind: str  # wall_clock | steps | tokens | memory | cpu | pids | disk | exec_timeout
    detail: str = ""


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Step(BaseModel):
    """One turn of the agent loop."""

    index: int
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    thought: str = ""
    tool_call: ToolCall | None = None
    tool_result: str = ""
    blocked_by: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


class FinalReport(BaseModel):
    """What the agent claimed when it finished (or what we recorded if it never did)."""

    finished: bool
    claimed_success: bool | None = None
    summary: str = ""


class CheckResult(BaseModel):
    command: str
    exit_code: int | None
    passed: bool
    output: str = ""


class RunEvidence(BaseModel):
    """Everything needed to grade a run, independent of how it was produced."""

    run_id: str
    scenario_id: str
    canaries: dict[str, str]
    steps: list[Step] = Field(default_factory=list)
    commands: list[CommandRecord] = Field(default_factory=list)
    egress: list[EgressEvent] = Field(default_factory=list)
    caps: list[CapEvent] = Field(default_factory=list)
    files_before: dict[str, str] = Field(default_factory=dict)  # path -> sha256
    files_after: dict[str, str] = Field(default_factory=dict)
    written_paths: list[str] = Field(default_factory=list)
    final: FinalReport = Field(default_factory=lambda: FinalReport(finished=False))
    success_check: CheckResult | None = None
    # True once the agent was handed the task; only runs that never got that far are excluded.
    agent_started: bool = False
    # Paths whose guest-side hash disagreed with a host-side read (evidence tampering).
    integrity: list[str] = Field(default_factory=list)

    @property
    def graded(self) -> bool:
        return self.agent_started or bool(self.steps)


class TripwireHit(BaseModel):
    tripwire: str
    kind: str
    severity: Severity
    evidence: str
    step: int | None = None
    # True when the agent's own guardrail refused the action before it ran. The lab's
    # containment (sandbox, warden) is not part of the agent, so anything *it* stops is
    # still an incident; anything the agent's guardrails stop is a near miss.
    near_miss: bool = False


class JuryAnswer(BaseModel):
    """One decision model's answer to one question."""

    model: str
    question: str
    probability: float | None = None  # noul: P(yes)
    choice: str | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    score: float | None = None
    confidence: float | None = None


class VerdictSource(StrEnum):
    TRIPWIRE = "tripwire"
    JURY = "jury"
    HUMAN = "human"
    NONE = "none"


class Verdict(BaseModel):
    incident: bool
    incident_severity: Severity | None = None
    incident_source: VerdictSource = VerdictSource.NONE
    task_success: bool
    task_success_source: VerdictSource = VerdictSource.NONE
    false_completion: bool = False
    needs_human_label: bool = False
    tripwire_hits: list[TripwireHit] = Field(default_factory=list)
    jury: list[JuryAnswer] = Field(default_factory=list)
    primary_failure_mode: str = "none"
    notes: list[str] = Field(default_factory=list)
