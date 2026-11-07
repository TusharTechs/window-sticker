"""A crash test: many runs of one agent across a trap suite, aggregated into a rating.

Aggregation works on ``RunSummary`` rows so the same code rates a live test, a stored
test, and a stored test after human labels have been applied.
"""

from __future__ import annotations

import asyncio
import itertools
import secrets
from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime

from windowsticker.agents.config import AgentConfig
from windowsticker.agents.reference import EventSink, _noop
from windowsticker.domain import utcnow
from windowsticker.grading.fusion import is_serious
from windowsticker.inference.client import InferenceClient
from windowsticker.runner.run import RunBudget, RunRecord, execute_run
from windowsticker.sandbox.base import SandboxDriver
from windowsticker.stats.intervals import RateEstimate, estimate_rate
from windowsticker.stats.rating import Rating, rate
from windowsticker.traps.loader import TrapSuite
from windowsticker.warden.proxy import EgressWarden

RecordSink = Callable[[RunRecord], Awaitable[None]]


@dataclass
class CrashTest:
    agent: AgentConfig
    suite: TrapSuite
    runs: int
    scenarios: list[str] | None = None  # default: whole suite, round-robin
    # microVMs alive at once on this host. Keep at or below the model's 16-at-once limit;
    # beyond it the API queues requests server-side (up to two minutes) rather than failing.
    sandbox_concurrency: int = 8
    image: str = "python"
    cpus: int = 1
    memory_mib: int = 1024
    budget: RunBudget = field(default_factory=RunBudget)
    test_id: str = field(default_factory=lambda: "test_" + secrets.token_hex(5))


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    scenario_id: str
    graded: bool  # False when the run errored before the agent acted
    incident: bool
    serious: bool
    task_success: bool
    near_miss: bool
    needs_label: bool
    failure_mode: str
    cost_usd: float
    boot_s: float
    teardown_verified: bool

    @property
    def safe_success(self) -> bool:
        return self.task_success and not self.incident


def summarize(r: RunRecord) -> RunSummary:
    v = r.verdict
    return RunSummary(
        run_id=r.run_id,
        scenario_id=r.scenario_id,
        graded=bool(r.evidence.steps),
        incident=v.incident,
        serious=is_serious(v),
        task_success=v.task_success,
        near_miss=any(h.near_miss for h in v.tripwire_hits),
        needs_label=v.needs_human_label,
        failure_mode=v.primary_failure_mode,
        cost_usd=r.cost_usd,
        boot_s=r.timings.boot_s,
        teardown_verified=r.teardown_verified,
    )


def apply_label(s: RunSummary, incident: bool) -> RunSummary:
    """A human label decides the incident outcome; serious follows it conservatively."""
    return replace(s, incident=incident, serious=incident, needs_label=False)


@dataclass
class ScenarioBreakdown:
    scenario_id: str
    runs: int
    incidents: int
    serious: int
    successes: int
    near_misses: int


@dataclass
class TestResult:
    test_id: str
    agent: AgentConfig
    suite_name: str
    suite_digest: str
    started_at: datetime
    finished_at: datetime
    summaries: list[RunSummary]
    rating: Rating
    breakdown: list[ScenarioBreakdown]
    failure_modes: dict[str, int]
    total_cost_usd: float
    cost_per_success_usd: float | None
    excluded_runs: int
    needs_label: int
    teardown_verified: bool
    median_boot_s: float | None
    records: list[RunRecord] = field(default_factory=list)

    def scenario_rate(self, scenario_id: str) -> RateEstimate | None:
        rs = [s for s in self.summaries if s.graded and s.scenario_id == scenario_id]
        return estimate_rate(sum(s.incident for s in rs), len(rs)) if rs else None


def plan_scenarios(suite: TrapSuite, runs: int, only: list[str] | None) -> list[str]:
    ids = only or suite.ids
    for sid in ids:
        suite.get(sid)  # validate
    return list(itertools.islice(itertools.cycle(ids), runs))


def aggregate(
    *,
    test_id: str,
    agent: AgentConfig,
    suite_name: str,
    suite_digest: str,
    summaries: list[RunSummary],
    started_at: datetime,
    finished_at: datetime | None = None,
    records: list[RunRecord] | None = None,
) -> TestResult:
    graded = [s for s in summaries if s.graded]
    n = len(graded)
    any_inc = sum(s.incident for s in graded)
    serious = sum(s.serious for s in graded)
    safe = sum(s.safe_success for s in graded)
    rating = rate(serious, any_inc, safe, n) if n else rate(0, 0, 0, 1)
    per: dict[str, list[RunSummary]] = defaultdict(list)
    for s in graded:
        per[s.scenario_id].append(s)
    breakdown = [
        ScenarioBreakdown(
            scenario_id=sid,
            runs=len(rs),
            incidents=sum(s.incident for s in rs),
            serious=sum(s.serious for s in rs),
            successes=sum(s.task_success for s in rs),
            near_misses=sum(s.near_miss for s in rs),
        )
        for sid, rs in sorted(per.items())
    ]
    total_cost = sum(s.cost_usd for s in summaries)
    boots = sorted(s.boot_s for s in summaries if s.boot_s)
    return TestResult(
        test_id=test_id,
        agent=agent,
        suite_name=suite_name,
        suite_digest=suite_digest,
        started_at=started_at,
        finished_at=finished_at or utcnow(),
        summaries=summaries,
        rating=rating,
        breakdown=breakdown,
        failure_modes=dict(Counter(s.failure_mode for s in graded if s.incident)),
        total_cost_usd=total_cost,
        cost_per_success_usd=(total_cost / safe) if safe else None,
        excluded_runs=len(summaries) - n,
        needs_label=sum(s.needs_label for s in graded),
        teardown_verified=all(s.teardown_verified for s in summaries),
        median_boot_s=boots[len(boots) // 2] if boots else None,
        records=records or [],
    )


async def run_crash_test(
    test: CrashTest,
    *,
    driver: SandboxDriver,
    client: InferenceClient,
    warden: EgressWarden,
    events: EventSink = _noop,
    on_record: RecordSink | None = None,
) -> TestResult:
    started_at = utcnow()
    plan = plan_scenarios(test.suite, test.runs, test.scenarios)
    sandbox_slots = asyncio.Semaphore(test.sandbox_concurrency)
    await events("test.started", {"test_id": test.test_id, "runs": len(plan)})

    async def one(sid: str) -> RunRecord:
        async with sandbox_slots:
            rec = await execute_run(
                suite=test.suite,
                scenario=test.suite.get(sid),
                agent=test.agent,
                driver=driver,
                client=client,
                warden=warden,
                image=test.image,
                cpus=test.cpus,
                memory_mib=test.memory_mib,
                budget=test.budget,
                test_id=test.test_id,
                events=events,
            )
        if on_record is not None:
            await on_record(rec)
        return rec

    records = list(await asyncio.gather(*(one(sid) for sid in plan)))
    result = aggregate(
        test_id=test.test_id,
        agent=test.agent,
        suite_name=test.suite.name,
        suite_digest=test.suite.digest,
        summaries=[summarize(r) for r in records],
        started_at=started_at,
        records=records,
    )
    await events("test.finished", {"test_id": test.test_id, "stars": result.rating.stars})
    return result
