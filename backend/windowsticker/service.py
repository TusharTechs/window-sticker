"""Application services shared by the API and the worker."""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import func, select

from windowsticker.agents.config import AgentConfig
from windowsticker.artifacts import record_json
from windowsticker.db.models import LabelRow, RunRow, TestRow
from windowsticker.db.session import Database
from windowsticker.domain import utcnow
from windowsticker.grading.fusion import is_serious
from windowsticker.runner.run import RunRecord
from windowsticker.runner.test import RunSummary, TestResult, aggregate, apply_label
from windowsticker.sticker.render import sticker_data
from windowsticker.traps.loader import TrapSuite, load_suite

MAX_RUNS_PER_TEST = 1000


def new_test_id() -> str:
    return "test_" + secrets.token_hex(5)


async def create_test(
    db: Database,
    agent: AgentConfig,
    runs: int,
    *,
    suite: str = "v1",
    scenarios: list[str] | None = None,
    concurrency: int = 8,
    label: str = "",
    precomputed: bool = False,
) -> TestRow:
    if not 1 <= runs <= MAX_RUNS_PER_TEST:
        raise ValueError(f"runs must be between 1 and {MAX_RUNS_PER_TEST}")
    trap_suite = load_suite(suite)
    for sid in scenarios or []:
        trap_suite.get(sid)
    row = TestRow(
        id=new_test_id(),
        status="queued",
        agent=agent.model_dump(),
        agent_name=agent.name,
        agent_fingerprint=agent.fingerprint(),
        model=agent.model,
        suite=suite,
        suite_digest=trap_suite.digest,
        runs_requested=runs,
        scenarios=scenarios or [],
        concurrency=max(1, min(concurrency, 16)),
        label=label,
        precomputed=precomputed,
    )
    async with db.session() as s:
        s.add(row)
        await s.commit()
    await db.add_event(row.id, "test.queued", {"runs": runs})
    return row


def run_row(test_id: str, rec: RunRecord) -> RunRow:
    v = rec.verdict
    return RunRow(
        id=rec.run_id,
        test_id=test_id,
        scenario_id=rec.scenario_id,
        status="finished",
        host_id=rec.host_id,
        sandbox_name=rec.sandbox_name,
        incident=v.incident,
        serious=is_serious(v),
        task_success=v.task_success,
        needs_label=v.needs_human_label,
        failure_mode=v.primary_failure_mode,
        cost_usd=rec.cost_usd,
        boot_s=rec.timings.boot_s,
        total_s=rec.timings.total_s,
        teardown_verified=rec.teardown_verified,
        graded=bool(rec.evidence.steps),
        record=record_json(rec),
    )


async def save_run(db: Database, test_id: str, rec: RunRecord) -> None:
    async with db.session() as s:
        s.add(run_row(test_id, rec))
        await s.commit()


def summary_from_row(row: RunRow) -> RunSummary:
    hits = row.record.get("verdict", {}).get("tripwire_hits", [])
    return RunSummary(
        run_id=row.id,
        scenario_id=row.scenario_id,
        graded=row.graded,
        incident=row.incident,
        serious=row.serious,
        task_success=row.task_success,
        near_miss=any(h.get("near_miss") for h in hits),
        needs_label=row.needs_label,
        failure_mode=row.failure_mode,
        cost_usd=row.cost_usd,
        boot_s=row.boot_s,
        teardown_verified=row.teardown_verified,
    )


async def result_for(db: Database, test: TestRow) -> TestResult:
    """Re-aggregate a stored test, applying the latest human label for each run."""
    async with db.session() as s:
        rows = (await s.execute(select(RunRow).where(RunRow.test_id == test.id))).scalars().all()
        labels = (
            (
                await s.execute(
                    select(LabelRow)
                    .join(RunRow, RunRow.id == LabelRow.run_id)
                    .where(RunRow.test_id == test.id)
                    .order_by(LabelRow.at)
                )
            )
            .scalars()
            .all()
        )
    latest = {lab.run_id: lab.incident for lab in labels}
    summaries = []
    for row in rows:
        summ = summary_from_row(row)
        if row.id in latest:
            summ = apply_label(summ, latest[row.id])
        summaries.append(summ)
    return aggregate(
        test_id=test.id,
        agent=AgentConfig.model_validate(test.agent),
        suite_name=test.suite,
        suite_digest=test.suite_digest,
        summaries=summaries,
        started_at=test.started_at or test.created_at,
        finished_at=test.finished_at,
    )


async def refresh_sticker(
    db: Database, test_id: str, suite: TrapSuite | None = None
) -> dict[str, Any]:
    async with db.session() as s:
        test = await s.get(TestRow, test_id)
        if test is None:
            raise KeyError(test_id)
    result = await result_for(db, test)
    data = sticker_data(result, suite or load_suite(test.suite))
    data["precomputed"] = test.precomputed
    data["label"] = test.label
    async with db.session() as s:
        t = await s.get(TestRow, test_id)
        assert t is not None
        t.sticker = data
        await s.commit()
    return data


async def label_run(
    db: Database, run_id: str, incident: bool, labeller: str, note: str = ""
) -> str:
    async with db.session() as s:
        run = await s.get(RunRow, run_id)
        if run is None:
            raise KeyError(run_id)
        s.add(LabelRow(run_id=run_id, incident=incident, labeller=labeller, note=note))
        run.needs_label = False
        await s.commit()
        test_id = run.test_id
    await refresh_sticker(db, test_id)
    await db.add_event(test_id, "run.labelled", {"incident": incident}, run_id=run_id)
    return test_id


async def finish_test(db: Database, test_id: str, error: str | None = None) -> None:
    async with db.session() as s:
        t = await s.get(TestRow, test_id)
        assert t is not None
        t.status = "failed" if error else "finished"
        t.error = error
        t.finished_at = utcnow()
        await s.commit()
    await refresh_sticker(db, test_id)


async def run_counts(db: Database, test_id: str) -> dict[str, int]:
    async with db.session() as s:
        total = await s.scalar(
            select(func.count()).select_from(RunRow).where(RunRow.test_id == test_id)
        )
        incidents = await s.scalar(
            select(func.count())
            .select_from(RunRow)
            .where(RunRow.test_id == test_id, RunRow.incident)
        )
    return {"finished": int(total or 0), "incidents": int(incidents or 0)}
