"""Render the sticker (full label) and the README badge as standalone SVG."""

from __future__ import annotations

from html import escape
from typing import Any

from windowsticker.runner.test import TestResult
from windowsticker.traps.loader import TrapSuite

INK = "#111418"
MUTED = "#5b6470"
RULE = "#d7dbe0"
PAPER = "#fbfaf6"
ACCENT = "#0b5cff"
STAR_ON = "#f5a400"
STAR_OFF = "#d9dde3"
RED = "#c62828"


def sticker_data(result: TestResult, suite: TrapSuite) -> dict[str, Any]:
    """Everything printed on a sticker, as JSON (also served by the API)."""
    r = result.rating
    sp, slo, shi = r.serious.per_thousand()
    ap, alo, ahi = r.any_incident.per_thousand()
    titles = {s.id: s.title for s in suite.scenarios}
    cats = {s.id: s.category.value for s in suite.scenarios}
    return {
        "test_id": result.test_id,
        "agent": {
            "name": result.agent.name,
            "model": result.agent.model,
            "guardrails": result.agent.guardrails,
            "fingerprint": result.agent.fingerprint(),
        },
        "suite": {"name": result.suite_name, "digest": result.suite_digest},
        "stars": r.stars,
        "provisional": r.provisional,
        "rating_reason": r.reason,
        "runs": r.serious.trials,
        "excluded_runs": result.excluded_runs,
        "serious_per_1000": {"point": sp, "lower": slo, "upper": shi},
        "any_per_1000": {"point": ap, "lower": alo, "upper": ahi},
        "task_success": {
            "point": r.task_success.point,
            "lower": r.task_success.lower,
            "upper": r.task_success.upper,
        },
        "total_cost_usd": result.total_cost_usd,
        "cost_per_success_usd": result.cost_per_success_usd,
        "median_boot_s": result.median_boot_s,
        "teardown_verified": result.teardown_verified,
        "needs_label": result.needs_label,
        "failure_modes": result.failure_modes,
        "breakdown": [
            {
                "scenario": b.scenario_id,
                "title": titles.get(b.scenario_id, b.scenario_id),
                "category": cats.get(b.scenario_id, ""),
                "runs": b.runs,
                "incidents": b.incidents,
                "serious": b.serious,
                "successes": b.successes,
                "near_misses": b.near_misses,
            }
            for b in result.breakdown
        ],
        "tested_at": result.finished_at.isoformat(),
    }


def _star(cx: float, cy: float, r: float, fill: str) -> str:
    import math

    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append(f"{cx + rad * math.cos(ang):.1f},{cy + rad * math.sin(ang):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'


def _money(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"${v:.4f}" if v < 0.1 else f"${v:.2f}"


def render_sticker(data: dict[str, Any]) -> str:
    w = 720
    rows = data["breakdown"]
    h = 520 + 26 * len(rows)
    a = data["agent"]
    s = data["serious_per_1000"]
    anyi = data["any_per_1000"]
    ts = data["task_success"]
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'font-family="Inter, Helvetica, Arial, sans-serif" role="img" '
        f'aria-label="Window Sticker for {escape(a["name"])}">',
        f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{PAPER}" stroke="{INK}" stroke-width="2"/>',
        f'<rect x="1" y="1" width="{w - 2}" height="56" rx="14" fill="{INK}"/>',
        f'<rect x="1" y="40" width="{w - 2}" height="17" fill="{INK}"/>',
        '<text x="28" y="37" fill="#fff" font-size="20" font-weight="800" letter-spacing="2">WINDOW STICKER</text>',
        f'<text x="{w - 28}" y="37" fill="#9aa4b2" font-size="13" text-anchor="end" letter-spacing="1">'
        "AI AGENT CRASH TEST</text>",
        f'<text x="28" y="92" fill="{INK}" font-size="24" font-weight="700">{escape(a["name"])}</text>',
        f'<text x="28" y="116" fill="{MUTED}" font-size="13">model {escape(a["model"])} · '
        f"config {escape(a['fingerprint'])} · guardrails: {escape(', '.join(a['guardrails']) or 'none')}</text>",
        f'<line x1="28" y1="134" x2="{w - 28}" y2="134" stroke="{RULE}"/>',
        f'<text x="28" y="164" fill="{MUTED}" font-size="12" letter-spacing="1">SAFETY RATING</text>',
    ]
    if data["provisional"]:
        out.append(
            f'<text x="28" y="212" fill="{INK}" font-size="30" font-weight="800">Provisional</text>'
        )
    else:
        for i in range(5):
            out.append(_star(48 + i * 46, 200, 20, STAR_ON if i < data["stars"] else STAR_OFF))
    out += [
        f'<text x="28" y="246" fill="{MUTED}" font-size="12">{escape(data["rating_reason"])[:110]}</text>',
        f'<text x="400" y="164" fill="{MUTED}" font-size="12" letter-spacing="1">SERIOUS INCIDENTS</text>',
        f'<text x="400" y="206" fill="{RED if s["point"] else INK}" font-size="40" font-weight="800">{s["point"]:.0f}</text>',
        f'<text x="400" y="228" fill="{INK}" font-size="13">per 1,000 runs · 95% CI {s["lower"]:.0f}–{s["upper"]:.0f}</text>',
        f'<line x1="28" y1="266" x2="{w - 28}" y2="266" stroke="{RULE}"/>',
    ]
    cells = [
        ("ANY INCIDENT", f"{anyi['point']:.0f}/1k", f"CI {anyi['lower']:.0f}–{anyi['upper']:.0f}"),
        (
            "TASK SUCCESS",
            f"{ts['point'] * 100:.0f}%",
            f"CI {ts['lower'] * 100:.0f}–{ts['upper'] * 100:.0f}%",
        ),
        ("COST / SAFE SUCCESS", _money(data["cost_per_success_usd"]), "inference, measured"),
        ("TEST COST", _money(data["total_cost_usd"]), f"{data['runs']} runs"),
    ]
    for i, (label, big, small) in enumerate(cells):
        x = 28 + i * 170
        out += [
            f'<text x="{x}" y="292" fill="{MUTED}" font-size="11" letter-spacing="1">{label}</text>',
            f'<text x="{x}" y="324" fill="{INK}" font-size="26" font-weight="700">{escape(big)}</text>',
            f'<text x="{x}" y="344" fill="{MUTED}" font-size="12">{escape(small)}</text>',
        ]
    y = 380
    out += [
        f'<line x1="28" y1="{y - 16}" x2="{w - 28}" y2="{y - 16}" stroke="{RULE}"/>',
        f'<text x="28" y="{y + 6}" fill="{MUTED}" font-size="11" letter-spacing="1">BY TRAP</text>',
        f'<text x="{w - 28}" y="{y + 6}" fill="{MUTED}" font-size="11" text-anchor="end">incidents / runs</text>',
    ]
    y += 30
    for row in rows:
        frac = row["incidents"] / row["runs"] if row["runs"] else 0
        bar_w = 200
        out += [
            f'<text x="28" y="{y}" fill="{INK}" font-size="13">{escape(row["title"])[:58]}</text>',
            f'<rect x="{w - 28 - bar_w - 60}" y="{y - 11}" width="{bar_w}" height="12" rx="6" fill="{RULE}"/>',
            f'<rect x="{w - 28 - bar_w - 60}" y="{y - 11}" width="{max(frac * bar_w, 0):.1f}" height="12" rx="6" fill="{RED}"/>',
            f'<text x="{w - 28}" y="{y}" fill="{INK}" font-size="13" text-anchor="end">{row["incidents"]}/{row["runs"]}</text>',
        ]
        y += 26
    y += 14
    foot = (
        f"Trap Suite {data['suite']['name']} ({data['suite']['digest']}) · {data['runs']} graded runs"
        f" · {data['excluded_runs']} excluded · tested {data['tested_at'][:10]}"
        f" · each run in its own microVM on Vultr, destroyed after use"
    )
    out += [
        f'<line x1="28" y1="{y - 6}" x2="{w - 28}" y2="{y - 6}" stroke="{RULE}"/>',
        f'<text x="28" y="{y + 14}" fill="{MUTED}" font-size="11">{escape(foot)}</text>',
        "</svg>",
    ]
    return "\n".join(out)


def render_badge(data: dict[str, Any]) -> str:
    left = "agent crash test"
    if data["provisional"]:
        right, color = "provisional", "#6b7280"
    else:
        stars = data["stars"]
        right = "★" * stars + "☆" * (5 - stars)
        color = {5: "#16a34a", 4: "#65a30d", 3: "#ca8a04", 2: "#ea580c"}.get(stars, "#dc2626")
    lw, rw = 112, 84
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw + rw}" height="20" role="img" '
        f'aria-label="{left}: {right}">'
        f'<rect width="{lw}" height="20" rx="3" fill="#2b2f36"/>'
        f'<rect x="{lw}" width="{rw}" height="20" rx="3" fill="{color}"/>'
        f'<rect x="{lw}" width="4" height="20" fill="{color}"/>'
        '<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="8" y="14">{left}</text><text x="{lw + 8}" y="14">{right}</text></g></svg>'
    )
