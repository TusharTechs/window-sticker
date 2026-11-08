"""The GitHub Action client (action/run.py) is standard-library only; test its logic here."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "wsk_action", Path(__file__).parents[2] / "action" / "run.py"
)
action = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(action)

STICKER = {
    "agent": {"name": "Bot", "model": "m", "fingerprint": "abc", "guardrails": []},
    "suite": {"name": "v1", "digest": "d"},
    "stars": 2,
    "provisional": False,
    "rating_reason": "Serious-incident rate is at most 18.7% with 95% confidence.",
    "runs": 36,
    "excluded_runs": 0,
    "serious_per_1000": {"point": 55.6, "lower": 6.8, "upper": 186.6},
    "any_per_1000": {"point": 83.3, "lower": 17.5, "upper": 224.7},
    "task_success": {"point": 0.94, "lower": 0.81, "upper": 0.99},
    "total_cost_usd": 0.13,
    "cost_per_success_usd": 0.0037,
    "breakdown": [
        {"title": "Rogue index", "incidents": 2, "runs": 3},
        {"title": "Clean", "incidents": 0, "runs": 3},
    ],
}


def test_agent_from_env_reference_and_opencode(tmp_path):
    prompt = tmp_path / "p.md"
    prompt.write_text("Be careful.")
    env = {"WSK_AGENT_NAME": "Bot", "WSK_GUARDRAILS": "a, b,", "WSK_PROMPT_FILE": str(prompt)}
    assert action.agent_from_env(env) == {
        "name": "Bot",
        "adapter": "reference",
        "model": "deepseek-v4.1-flash-1017",
        "guardrails": ["a", "b"],
        "system_prompt": "Be careful.",
    }
    oc = action.agent_from_env(
        {"WSK_AGENT_NAME": "OC", "WSK_ADAPTER": "opencode", "WSK_GUARDRAILS": "a"}
    )
    assert "guardrails" not in oc and oc["adapter"] == "opencode"


def test_summary_lists_only_traps_with_incidents():
    md = action.summary_markdown(STICKER, "https://x/tests/t", "https://x/b.svg")
    assert "★★☆☆☆" in md and "56 per 1,000" in md and "95% CI 7–187" in md
    assert "| Rogue index | 2/3 |" in md and "Clean" not in md


@pytest.mark.parametrize("min_stars,expected", [(0, 0), (2, 0), (3, 1)])
def test_main_waits_publishes_and_gates(tmp_path, monkeypatch, min_stars, expected):
    calls = []
    statuses = iter(["queued", "running", "finished"])

    def fake_req(method, url, token=None, body=None):
        calls.append((method, url, body))
        if method == "POST" and url.endswith("/api/tests"):
            return {"id": "test_1"}
        if url.endswith("/sticker.json"):
            return STICKER
        if url.endswith("/api/tests/test_1"):
            return {"status": next(statuses), "runs_requested": 36, "progress": {"finished": 36}}
        if "/issues/" in url:
            return {}
        raise AssertionError(url)

    monkeypatch.setattr(action, "_req", fake_req)
    monkeypatch.setattr(action.time, "sleep", lambda s: None)
    summary, outputs, event = tmp_path / "summary.md", tmp_path / "out", tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 7}}))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    env = {
        "WSK_SERVER": "https://x/",
        "WSK_TOKEN": "tok",
        "WSK_AGENT_NAME": "Bot",
        "WSK_RUNS": "36",
        "WSK_SCENARIOS": "a,b",
        "WSK_MIN_STARS": str(min_stars),
        "GITHUB_STEP_SUMMARY": str(summary),
    }
    assert action.main(env) == expected
    post = calls[0]
    assert post[2]["scenarios"] == ["a", "b"] and post[2]["runs"] == 36
    assert "★★☆☆☆" in summary.read_text()
    assert "test-id=test_1" in outputs.read_text() and "stars=2" in outputs.read_text()
    assert any("/repos/o/r/issues/7/comments" in c[1] for c in calls)


@pytest.mark.parametrize(
    "significant, change, expected", [(True, 0.08, 1), (False, 0.05, 0), (True, -0.08, 0)]
)
def test_baseline_gate_fails_only_on_a_measurable_regression(
    tmp_path, monkeypatch, significant, change, expected
):
    def fake_req(method, url, token=None, body=None):
        if method == "POST":
            return {"id": "test_new"}
        if url.endswith("/sticker.json"):
            return STICKER
        if url.endswith("/api/tests/test_new"):
            return {"status": "finished", "runs_requested": 48, "progress": {"finished": 48}}
        if "/api/compare?a=test_main&b=test_new" in url:
            return {
                "p_value": 0.01,
                "significant": significant,
                "absolute_change": change,
                "verdict": "v",
            }
        raise AssertionError(url)

    monkeypatch.setattr(action, "_req", fake_req)
    monkeypatch.setattr(action.time, "sleep", lambda s: None)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    env = {
        "WSK_SERVER": "https://x",
        "WSK_TOKEN": "tok",
        "WSK_AGENT_NAME": "Bot",
        "WSK_COMMENT": "false",
        "WSK_BASELINE_TEST": "test_main",
    }
    assert action.main(env) == expected
