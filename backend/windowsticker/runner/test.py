"""A crash test: many runs of one agent across a trap suite, aggregated into a rating."""

from __future__ import annotations

import asyncio
import itertools
import secrets
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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
    records: list[RunRecord]
    rating: Rating
    breakdown: list[ScenarioBreakdown]
    failure_modes: dict[str, int]
    total_cost_usd: float
    cost_per_success_usd: float | None
    excluded_runs: int
    needs_label: int
    teardown_verified: bool
    median_boot_s: float | None

    @property
    def graded(self) -> list[RunRecord]:
        return [r for r in self.records if r.evidence.steps]

    def scenario_rate(self, scenario_id: str) -> RateEstimate | None:
        rs = [r for r in self.graded if r.scenario_id == scenario_id]
        return estimate_rate(sum(r.verdict.incident for r in rs), len(rs)) if rs else None


def plan_scenarios(suite: TrapSuite, runs: int, only: list[str] | None) -> list[str]:
    ids = only or suite.ids
    for sid in ids:
        suite.get(sid)  # validate
    return list(itertools.islice(itertools.cycle(ids), runs))


def aggregate(test: CrashTest, records: list[RunRecord], started_at: datetime) -> TestResult:
    graded = [r for r in records if r.evidence.steps]
    n = len(graded)
    any_inc = sum(r.verdict.incident for r in graded)
    serious = sum(is_serious(r.verdict) for r in graded)
    succ = sum(r.verdict.task_success and not r.verdict.incident for r in graded)
    rating = rate(serious, any_inc, succ, n) if n else rate(0, 0, 0, 1)
    per: dict[str, list[RunRecord]] = defaultdict(list)
    for r in graded:
        per[r.scenario_id].append(r)
    breakdown = [
        ScenarioBreakdown(
            scenario_id=sid,
            runs=len(rs),
            incidents=sum(r.verdict.incident for r in rs),
            serious=sum(is_serious(r.verdict) for r in rs),
            successes=sum(r.verdict.task_success for r in rs),
            near_misses=sum(any(h.near_miss for h in r.verdict.tripwire_hits) for r in rs),
        )
        for sid, rs in sorted(per.items())
    ]
    modes = Counter(r.verdict.primary_failure_mode for r in graded if r.verdict.incident)
    total_cost = sum(r.cost_usd for r in records)
    boots = sorted(r.timings.boot_s for r in records if r.timings.boot_s)
    return TestResult(
        test_id=test.test_id,
        agent=test.agent,
        suite_name=test.suite.name,
        suite_digest=test.suite.digest,
        started_at=started_at,
        finished_at=utcnow(),
        records=records,
        rating=rating,
        breakdown=breakdown,
        failure_modes=dict(modes),
        total_cost_usd=total_cost,
        cost_per_success_usd=(total_cost / succ) if succ else None,
        excluded_runs=len(records) - n,
        needs_label=sum(r.verdict.needs_human_label for r in graded),
        teardown_verified=all(r.teardown_verified for r in records),
        median_boot_s=boots[len(boots) // 2] if boots else None,
    )


async def run_crash_test(
    test: CrashTest,
    *,
    driver: SandboxDriver,
    client: InferenceClient,
    warden: EgressWarden,
    events: EventSink = _noop,
) -> TestResult:
    started_at = utcnow()
    plan = plan_scenarios(test.suite, test.runs, test.scenarios)
    sandbox_slots = asyncio.Semaphore(test.sandbox_concurrency)
    await events("test.started", {"test_id": test.test_id, "runs": len(plan)})

    async def one(sid: str) -> RunRecord:
        async with sandbox_slots:
            return await execute_run(
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

    records = list(await asyncio.gather(*(one(sid) for sid in plan)))
    result = aggregate(test, records, started_at)
    await events("test.finished", {"test_id": test.test_id, "stars": result.rating.stars})
    return result
