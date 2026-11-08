"""GitHub Action entry point: start a crash test, wait, publish the sticker.

Standard library only, so it runs on any runner without installing anything.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

FINAL = {"finished", "failed", "cancelled"}


def _req(method: str, url: str, token: str | None = None, body: Any = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "window-sticker-action/1")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise SystemExit(f"{method} {url} failed: {exc.code} {detail}") from None


def agent_from_env(env: dict[str, str]) -> dict[str, Any]:
    adapter = env.get("WSK_ADAPTER", "reference") or "reference"
    agent: dict[str, Any] = {
        "name": env["WSK_AGENT_NAME"],
        "adapter": adapter,
        "model": env.get("WSK_MODEL") or "deepseek-v4.1-flash-1017",
    }
    if adapter == "reference":
        agent["guardrails"] = [g.strip() for g in env.get("WSK_GUARDRAILS", "").split(",") if g.strip()]
        prompt_file = env.get("WSK_PROMPT_FILE", "")
        if prompt_file:
            with open(prompt_file) as fh:
                agent["system_prompt"] = fh.read()
    return agent


def stars_text(s: dict[str, Any]) -> str:
    return "Provisional" if s["provisional"] else "★" * s["stars"] + "☆" * (5 - s["stars"])


def summary_markdown(s: dict[str, Any], test_url: str, badge_url: str) -> str:
    sp, anyi, ts = s["serious_per_1000"], s["any_per_1000"], s["task_success"]
    cps = s.get("cost_per_success_usd")
    lines = [
        f"## Window Sticker: {s['agent']['name']}",
        "",
        f"![agent crash test]({badge_url})",
        "",
        f"**{stars_text(s)}** · {s['rating_reason']}",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Serious incidents | **{sp['point']:.0f} per 1,000** (95% CI {sp['lower']:.0f}–{sp['upper']:.0f}) |",
        f"| Any incident | {anyi['point']:.0f} per 1,000 (95% CI {anyi['lower']:.0f}–{anyi['upper']:.0f}) |",
        f"| Safe task success | {ts['point'] * 100:.0f}% (95% CI {ts['lower'] * 100:.0f}–{ts['upper'] * 100:.0f}%) |",
        f"| Cost per safe success | {'n/a' if cps is None else f'${cps:.4f}'} |",
        f"| Test cost | ${s['total_cost_usd']:.4f} for {s['runs']} graded runs ({s['excluded_runs']} excluded) |",
        f"| Model / config | `{s['agent']['model']}` / `{s['agent']['fingerprint']}` |",
        f"| Trap suite | {s['suite']['name']} (`{s['suite']['digest']}`) |",
        "",
    ]
    hit = [b for b in s["breakdown"] if b["incidents"]]
    if hit:
        lines += ["| Trap | Incidents / runs |", "|---|---|"]
        lines += [f"| {b['title']} | {b['incidents']}/{b['runs']} |" for b in hit]
        lines.append("")
    lines.append(f"[Open the test, replay every run]({test_url})")
    return "\n".join(lines) + "\n"


def _output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as fh:
            fh.write(f"{name}={value}\n")


def _comment(markdown: str) -> None:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not (event_path and repo and token):
        return
    with open(event_path) as fh:
        event = json.load(fh)
    number = (event.get("pull_request") or {}).get("number")
    if not number:
        return
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    try:
        _req("POST", f"{api}/repos/{repo}/issues/{number}/comments", token, {"body": markdown})
    except SystemExit as exc:  # a missing permission should not fail the crash test
        print(f"::warning::could not comment on the pull request: {exc}")


def main(env: dict[str, str]) -> int:
    server = env["WSK_SERVER"].rstrip("/")
    token = env["WSK_TOKEN"]
    body: dict[str, Any] = {"agent": agent_from_env(env), "runs": int(env.get("WSK_RUNS") or 36)}
    scenarios = [x.strip() for x in env.get("WSK_SCENARIOS", "").split(",") if x.strip()]
    if scenarios:
        body["scenarios"] = scenarios
    test = _req("POST", f"{server}/api/tests", token, body)
    test_id = test["id"]
    test_url = f"{server}/tests/{test_id}"
    print(f"Started {test_id}: {test_url}")
    _output("test-id", test_id)
    _output("url", test_url)

    deadline = time.time() + 60 * float(env.get("WSK_TIMEOUT_MIN") or 45)
    last = -1
    while True:
        t = _req("GET", f"{server}/api/tests/{test_id}")
        done = (t.get("progress") or {}).get("finished", 0)
        if done != last:
            print(f"  {t['status']}: {done}/{t['runs_requested']} runs graded")
            last = done
        if t["status"] in FINAL:
            break
        if time.time() > deadline:
            print(f"::error::timed out waiting for {test_id}")
            return 1
        time.sleep(15)
    if t["status"] != "finished":
        print(f"::error::crash test {t['status']}: {t.get('error')}")
        return 1

    sticker = _req("GET", f"{server}/api/tests/{test_id}/sticker.json")
    markdown = summary_markdown(sticker, test_url, f"{server}/api/tests/{test_id}/badge.svg")
    if env.get("GITHUB_STEP_SUMMARY"):
        with open(env["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(markdown)
    print(markdown)
    _output("stars", str(sticker["stars"]))
    _output("serious-per-1000", f"{sticker['serious_per_1000']['point']:.1f}")
    if (env.get("WSK_COMMENT") or "true").lower() == "true":
        _comment(markdown)

    min_stars = int(env.get("WSK_MIN_STARS") or 0)
    if min_stars and (sticker["provisional"] or sticker["stars"] < min_stars):
        print(f"::error::rating {stars_text(sticker)} is below the required {min_stars} stars")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(dict(os.environ)))
