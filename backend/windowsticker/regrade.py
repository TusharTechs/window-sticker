"""Re-grade stored runs with the current tripwires, without re-running anything.

Evidence is immutable; graders improve. When a tripwire is fixed, every stored run can be
re-graded from its evidence (the jury's stored answers are reused, so no model is called)
and a new sticker is produced next to the old one, with the changes listed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from windowsticker.agents.config import AgentConfig
from windowsticker.domain import JuryAnswer, RunEvidence, utcnow
from windowsticker.grading.fusion import fuse, is_serious
from windowsticker.grading.tripwires import evaluate_tripwires
from windowsticker.runner.test import RunSummary, aggregate
from windowsticker.sticker.render import render_badge, render_sticker, sticker_data
from windowsticker.traps.loader import TrapSuite, load_suite


@dataclass(frozen=True)
class Change:
    run_id: str
    scenario_id: str
    was_incident: bool
    now_incident: bool


def regrade_dir(path: Path, suite: TrapSuite | None = None) -> tuple[dict[str, Any], list[Change]]:
    old = json.loads((path / "sticker.json").read_text())
    suite = suite or load_suite(old["suite"]["name"])
    agent_file = path / "agent.json"
    if agent_file.exists():
        agent = AgentConfig.model_validate_json(agent_file.read_text())
    else:
        a = old["agent"]
        agent = AgentConfig(name=a["name"], model=a["model"], guardrails=a["guardrails"])
    summaries: list[RunSummary] = []
    changes: list[Change] = []
    for line in (path / "runs.jsonl").read_text().splitlines():
        r = json.loads(line)
        evidence = RunEvidence.model_validate(r["evidence"])
        answers = [JuryAnswer.model_validate(a) for a in r["verdict"].get("jury", [])]
        sc = suite.get(r["scenario_id"])
        verdict = fuse(evidence, evaluate_tripwires(sc, evidence), answers, category=sc.category)
        if verdict.incident != r["verdict"]["incident"]:
            changes.append(
                Change(r["run_id"], r["scenario_id"], r["verdict"]["incident"], verdict.incident)
            )
        summaries.append(
            RunSummary(
                run_id=r["run_id"],
                scenario_id=r["scenario_id"],
                graded=evidence.graded,
                incident=verdict.incident,
                serious=is_serious(verdict),
                task_success=verdict.task_success,
                near_miss=any(h.near_miss for h in verdict.tripwire_hits),
                needs_label=verdict.needs_human_label,
                failure_mode=verdict.primary_failure_mode,
                cost_usd=float(r["cost_usd"]),
                boot_s=float(r["timings"]["boot_s"]),
                teardown_verified=bool(r["teardown_verified"]),
            )
        )
    result = aggregate(
        test_id=old["test_id"],
        agent=agent,
        suite_name=suite.name,
        suite_digest=suite.digest,
        summaries=summaries,
        started_at=utcnow(),
    )
    data = sticker_data(result, suite)
    data["agent"]["fingerprint"] = old["agent"]["fingerprint"]  # the agent that actually ran
    data["tested_at"] = old["tested_at"]
    data["regraded_at"] = utcnow().isoformat()
    data["regraded_from_suite_digest"] = old["suite"]["digest"]
    return data, changes


def write_regrade(path: Path, data: dict[str, Any], changes: list[Change]) -> None:
    (path / "sticker.regraded.json").write_text(json.dumps(data, indent=2))
    (path / "sticker.regraded.svg").write_text(render_sticker(data))
    (path / "badge.regraded.svg").write_text(render_badge(data))
    (path / "regrade-changes.json").write_text(json.dumps([c.__dict__ for c in changes], indent=2))
