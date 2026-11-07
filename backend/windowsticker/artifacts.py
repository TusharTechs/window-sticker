"""Write a crash test's outputs to disk: runs, result, sticker and badge."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from windowsticker.runner.run import RunRecord
from windowsticker.runner.test import TestResult
from windowsticker.sticker.render import render_badge, render_sticker, sticker_data
from windowsticker.traps.loader import TrapSuite


def record_json(r: RunRecord) -> dict[str, Any]:
    return {
        "run_id": r.run_id,
        "scenario_id": r.scenario_id,
        "agent_fingerprint": r.agent_fingerprint,
        "model": r.model,
        "host_id": r.host_id,
        "sandbox_name": r.sandbox_name,
        "evidence": r.evidence.model_dump(mode="json"),
        "verdict": r.verdict.model_dump(mode="json"),
        "agent_usage": asdict(r.agent_usage),
        "jury_usage": asdict(r.jury_usage),
        "cost_usd": r.cost_usd,
        "timings": asdict(r.timings),
        "teardown_verified": r.teardown_verified,
        "jury_raw": r.jury_raw,
        "errors": r.errors,
    }


def write_test(result: TestResult, suite: TrapSuite, out_dir: Path) -> Path:
    target = out_dir / result.test_id
    target.mkdir(parents=True, exist_ok=True)
    with (target / "runs.jsonl").open("w") as fh:
        for r in result.records:
            fh.write(json.dumps(record_json(r)) + "\n")
    data = sticker_data(result, suite)
    (target / "sticker.json").write_text(json.dumps(data, indent=2))
    (target / "sticker.svg").write_text(render_sticker(data))
    (target / "badge.svg").write_text(render_badge(data))
    return target
