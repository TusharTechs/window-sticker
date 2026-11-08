"""HTTP + WebSocket API for the web app, the CLI and the GitHub Action."""

from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from windowsticker import __version__
from windowsticker.agents.config import AgentConfig
from windowsticker.agents.guardrails import PROFILES, GuardrailEngine
from windowsticker.behaviour import profile as behaviour_profile
from windowsticker.db.models import EventRow, LabelRow, RunRow, TestRow
from windowsticker.db.session import Database
from windowsticker.environments import DEFAULT_ENVIRONMENT, ENVIRONMENTS
from windowsticker.service import create_test, is_internal, label_run, result_for, run_counts
from windowsticker.stats.ab import compare_rates
from windowsticker.stats.rating import MIN_TRIALS_FOR_RATING, THRESHOLDS, runs_needed_for
from windowsticker.sticker.render import render_badge, render_sticker, sticker_data
from windowsticker.traps.loader import load_suite
from windowsticker.traps.standards import CATEGORY_OWASP, OWASP_LLM_2025, owasp_for
from windowsticker.traps.variants import is_private as is_private_suite

SVG = "image/svg+xml"


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; Postgres returns aware ones. Both are UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class CreateTest(BaseModel):
    agent: AgentConfig
    runs: int = Field(48, ge=1, le=1000)
    suite: str = "v2"
    scenarios: list[str] = Field(default_factory=list)
    concurrency: int = Field(8, ge=1, le=16)
    label: str = ""


# The public live demo: a small, fixed-cost crash test anyone can start without a token.
DEMO_MODELS = ("deepseek-v4.1-flash-1017", "qwen3.8-flash-next", "minimax-m3.1-flash")
DEMO_TRAPS = ("pip-conf-index", "netcheck-dns-exfil", "dependency-confusion")
DEMO_RUNS = 6
DEMO_LABEL = "Live demo"
DEMO_PROFILE_NAMES = {
    "none": "no guardrails",
    "prompt-only": "prompt guardrail only",
    "hardened": "hardened",
}


class DemoIn(BaseModel):
    model: str = DEMO_MODELS[0]
    profile: Literal["none", "prompt-only", "hardened"] = "none"
    environment: str = DEFAULT_ENVIRONMENT


MATRIX_PREFIX = "Environment matrix "


class CreateMatrix(BaseModel):
    agent: AgentConfig
    environments: list[str] = Field(default_factory=lambda: list(ENVIRONMENTS), min_length=2)
    runs: int = Field(48, ge=1, le=1000)
    suite: str = "v2"
    scenarios: list[str] = Field(default_factory=list)
    concurrency: int = Field(8, ge=1, le=16)


class LabelIn(BaseModel):
    incident: bool
    labeller: str = Field(min_length=1, max_length=100)
    note: str = ""


def _test_out(t: TestRow, counts: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "id": t.id,
        "internal": is_internal(t),
        "imported": t.concurrency == 0,
        "scenarios": list(t.scenarios or []),
        "status": t.status,
        "agent_name": t.agent_name,
        "agent_fingerprint": t.agent_fingerprint,
        "model": t.model,
        "guardrails": (t.agent or {}).get("guardrails", []),
        "suite": t.suite,
        "suite_digest": t.suite_digest,
        "runs_requested": t.runs_requested,
        "concurrency": t.concurrency,
        "label": t.label,
        "environment": t.environment or DEFAULT_ENVIRONMENT,
        "environment_title": ENVIRONMENTS.get(
            t.environment or DEFAULT_ENVIRONMENT, ENVIRONMENTS[DEFAULT_ENVIRONMENT]
        ).title,
        "precomputed": t.precomputed,
        "worker": t.worker,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "finished_at": t.finished_at.isoformat() if t.finished_at else None,
        "error": t.error,
        "sticker": t.sticker,
        "progress": counts,
    }


def _run_out(r: RunRow, full: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id,
        "test_id": r.test_id,
        "scenario_id": r.scenario_id,
        "host_id": r.host_id,
        "sandbox_name": r.sandbox_name,
        "incident": r.incident,
        "serious": r.serious,
        "task_success": r.task_success,
        "needs_label": r.needs_label,
        "failure_mode": r.failure_mode,
        "cost_usd": r.cost_usd,
        "boot_s": r.boot_s,
        "total_s": r.total_s,
        "teardown_verified": r.teardown_verified,
        "graded": r.graded,
    }
    if full:
        out["record"] = r.record
    return out


class RateLimiter:
    """Fixed-window per-client limiter for the public API (behind Caddy, one hop)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._window = 0
        self._counts: dict[str, int] = {}

    def allow(self, client: str) -> bool:
        window = int(time.monotonic() // 60)
        if window != self._window:
            self._window, self._counts = window, {}
        self._counts[client] = self._counts.get(client, 0) + 1
        return self._counts[client] <= self.per_minute


def create_app(
    db: Database,
    *,
    admin_token: str | None = None,
    submit_token: str | None = None,
    label_token: str | None = None,
    max_runs_per_test: int = 240,
    requests_per_minute: int = 240,
    max_event_sockets: int = 64,
    cors_origins: list[str] | None = None,
    demo_daily_limit: int = 30,
    demo_cooldown_s: float = 600.0,
    evidence_store: Any = None,
) -> FastAPI:
    """Build the API. Reads are public. Writes need a bearer token, scoped by action:
    ``submit_token`` may start tests, ``label_token`` may label runs, ``admin_token`` may do
    both. With no token configured for an action, it is refused outright (fail closed)."""

    def _check(authorization: str | None, accepted: list[str], what: str) -> None:
        tokens = [t for t in accepted if t]
        if not tokens:
            raise HTTPException(503, f"{what} is disabled: no access token is configured")
        supplied = (authorization or "").removeprefix("Bearer ").strip().encode()
        if not any(hmac.compare_digest(supplied, t.encode()) for t in tokens):
            raise HTTPException(401, f"a valid access token is required to {what}")

    def require_submitter(authorization: str | None = Header(default=None)) -> None:
        _check(authorization, [submit_token or "", admin_token or ""], "start tests")

    def require_labeller(authorization: str | None = Header(default=None)) -> None:
        _check(authorization, [label_token or "", admin_token or ""], "label runs")

    require_writer = require_submitter
    limiter = RateLimiter(requests_per_minute)
    open_sockets: dict[str, int] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await db.create_all()
        yield
        await db.dispose()

    app = FastAPI(title="Window Sticker", version=__version__, lifespan=lifespan)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/api/"):
            # Caddy is the only proxy; its X-Forwarded-For first hop is the real client.
            client = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            client = client or (request.client.host if request.client else "?")
            if not limiter.allow(client):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_methods=["GET", "POST"],
        allow_credentials=False,
        allow_headers=["*"],
    )

    async def _get_test(test_id: str) -> TestRow:
        async with db.session() as s:
            t = await s.get(TestRow, test_id)
        if t is None:
            raise HTTPException(404, "test not found")
        return t

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "version": __version__,
            "writes_enabled": bool(admin_token or submit_token),
        }

    @app.get("/api/auth/check", dependencies=[Depends(require_writer)])
    async def auth_check() -> dict[str, bool]:
        return {"ok": True}

    # ------------------------------------------------------------------ suites
    @app.get("/api/suites/{name}")
    async def suite(name: str) -> dict[str, Any]:
        try:
            s = load_suite(name)
        except FileNotFoundError as exc:
            raise HTTPException(404, "suite not found") from exc
        private = is_private_suite(name)
        return {
            "name": s.name,
            "digest": s.digest,
            # A private variant's wording is the secret: only titles and categories are served.
            "private": private,
            "scenarios": [
                {
                    "id": sc.id,
                    "title": sc.title,
                    "category": sc.category.value,
                    "severity": sc.severity.value,
                    "summary": sc.summary,
                    "task": "(private variant: the wording is not published)"
                    if private
                    else sc.task,
                    "tripwires": []
                    if private
                    else [t.model_dump(mode="json") for t in sc.tripwires],
                    "tags": sc.tags,
                    "owasp": owasp_for(sc.category.value),
                }
                for sc in s.scenarios
            ],
        }

    @app.get("/api/measurements")
    async def measurements() -> dict[str, Any]:
        data: dict[str, Any] = json.loads(
            (Path(__file__).parents[1] / "measurements.json").read_text()
        )
        return data

    @app.get("/api/jury-report")
    async def jury_report() -> dict[str, Any]:
        data: dict[str, Any] = json.loads(
            (Path(__file__).parents[1] / "jury_report.json").read_text()
        )
        return data

    def _escape_file(profile: str, environment: str) -> Path | None:
        here = Path(__file__).parents[1]
        if profile == "agent":
            return here / "escape_matrix_agent.json"
        if profile != "reference":
            return None
        if environment == DEFAULT_ENVIRONMENT:
            return here / "escape_matrix.json"
        path = here / f"escape_matrix_{environment}.json"
        return path if path.exists() else None

    @app.get("/api/escape-matrix")
    async def escape_matrix(
        profile: str = "reference", environment: str = DEFAULT_ENVIRONMENT
    ) -> dict[str, Any]:
        """Measured escape matrix for a sandbox profile (reference, or agent: in-VM agent),
        on one of the environments' images."""
        path = _escape_file(profile, environment)
        if path is None:
            raise HTTPException(404, "no escape matrix for that profile and environment")
        data: dict[str, Any] = json.loads(path.read_text())
        return data

    @app.get("/api/standards")
    async def standards() -> dict[str, Any]:
        """The OWASP Top 10 for LLM Applications (2025) and which trap categories measure each."""
        return {
            "name": "OWASP Top 10 for LLM Applications 2025",
            "risks": [{"id": k, "name": v} for k, v in OWASP_LLM_2025.items()],
            "categories": {k: list(v) for k, v in CATEGORY_OWASP.items()},
        }

    @app.get("/api/methodology")
    async def methodology() -> dict[str, Any]:
        return {
            "confidence": 0.95,
            "interval": "Clopper-Pearson exact",
            "min_runs_for_rating": MIN_TRIALS_FOR_RATING,
            "stars": [
                {"stars": s, "max_upper_bound": lim, "clean_runs_needed": runs_needed_for(s)}
                for s, lim in THRESHOLDS
            ],
            "guardrails": sorted(GuardrailEngine.KNOWN),
            "profiles": PROFILES,
        }

    # ------------------------------------------------------------------ tests
    @app.post("/api/tests", status_code=201, dependencies=[Depends(require_writer)])
    async def post_test(body: CreateTest) -> dict[str, Any]:
        if body.runs > max_runs_per_test:
            raise HTTPException(422, f"at most {max_runs_per_test} runs per test")
        try:
            row = await create_test(
                db,
                body.agent,
                body.runs,
                suite=body.suite,
                scenarios=body.scenarios or None,
                concurrency=body.concurrency,
                label=body.label,
            )
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return _test_out(row)

    # ------------------------------------------------------------ environments
    @app.get("/api/environments")
    async def environments() -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for e in ENVIRONMENTS.values():
            path = _escape_file("reference", e.id)
            escape = None
            if path is not None:
                m = json.loads(path.read_text())
                escape = {"contained": m["contained"], "total": m["total"], "image": m.get("image")}
            out.append(
                {
                    "id": e.id,
                    "image": e.image,
                    "title": e.title,
                    "os": e.os,
                    "notes": e.notes,
                    "escape": escape,
                }
            )
        return out

    @app.post("/api/matrix", status_code=201, dependencies=[Depends(require_writer)])
    async def post_matrix(body: CreateMatrix) -> dict[str, Any]:
        """The same agent and traps, one test per environment, grouped as a matrix."""
        unknown = [e for e in body.environments if e not in ENVIRONMENTS]
        if unknown:
            raise HTTPException(422, f"unknown environment(s): {', '.join(unknown)}")
        if body.runs > max_runs_per_test:
            raise HTTPException(422, f"at most {max_runs_per_test} runs per test")
        matrix_id = "mx_" + secrets.token_hex(4)
        rows = []
        for env in dict.fromkeys(body.environments):
            rows.append(
                await create_test(
                    db,
                    body.agent,
                    body.runs,
                    suite=body.suite,
                    scenarios=body.scenarios or None,
                    concurrency=body.concurrency,
                    label=MATRIX_PREFIX + matrix_id,
                    environment=env,
                )
            )
        return {"matrix_id": matrix_id, "tests": [_test_out(r) for r in rows]}

    async def _matrix_tests(matrix_id: str | None = None) -> list[TestRow]:
        async with db.session() as s:
            q = select(TestRow).where(TestRow.label.startswith(MATRIX_PREFIX))
            if matrix_id:
                q = select(TestRow).where(TestRow.label == MATRIX_PREFIX + matrix_id)
            return list((await s.execute(q.order_by(TestRow.created_at))).scalars().all())

    def _matrix_out(matrix_id: str, rows: list[TestRow]) -> dict[str, Any]:
        order = list(ENVIRONMENTS)
        rows = sorted(
            rows, key=lambda t: order.index(t.environment) if t.environment in order else 99
        )
        base = next((t for t in rows if t.environment == DEFAULT_ENVIRONMENT), rows[0])
        out_rows = []
        for t in rows:
            row = _test_out(t)
            st, bs = t.sticker, base.sticker
            if st and bs and t is not base:

                def k(x: dict[str, Any], key: str) -> int:
                    return round(float(x[key]["point"]) * int(x["runs"]) / 1000)

                ser = compare_rates(
                    k(bs, "serious_per_1000"), bs["runs"], k(st, "serious_per_1000"), st["runs"]
                )
                anyi = compare_rates(
                    k(bs, "any_per_1000"), bs["runs"], k(st, "any_per_1000"), st["runs"]
                )
                row["versus_baseline"] = {
                    "serious_p": ser.p_value,
                    "any_p": anyi.p_value,
                    "serious_change_per_1000": ser.absolute_change * 1000,
                    "any_change_per_1000": anyi.absolute_change * 1000,
                    "changed": ser.significant or anyi.significant,
                }
            out_rows.append(row)
        # Several environments and two metrics are compared at once, so p-values are adjusted
        # with Holm's method before anything is called a change.
        tests_ = [
            (r["versus_baseline"], key)
            for r in out_rows
            if "versus_baseline" in r
            for key in ("serious_p", "any_p")
        ]
        ranked = sorted(tests_, key=lambda x: x[0][x[1]])
        running = 0.0
        for i, (vb, key) in enumerate(ranked):
            running = max(running, min(1.0, (len(ranked) - i) * vb[key]))
            vb[key + "_adjusted"] = running
        for r in out_rows:
            vb = r.get("versus_baseline")
            if vb:
                vb["changed"] = (
                    min(vb.get("serious_p_adjusted", 1.0), vb.get("any_p_adjusted", 1.0)) < 0.05
                )
        statuses = {t.status for t in rows}
        return {
            "matrix_id": matrix_id,
            "agent_name": base.agent_name,
            "model": base.model,
            "baseline": base.environment,
            "status": "running" if statuses & {"queued", "running"} else "finished",
            "created_at": rows[0].created_at.isoformat() if rows[0].created_at else None,
            "tests": out_rows,
        }

    behaviour_cache: dict[str, dict[str, Any]] = {}

    @app.get("/api/matrix/{matrix_id}/behaviour")
    async def matrix_behaviour(matrix_id: str) -> dict[str, Any]:
        """Per environment: tools the agent reached for that were missing, and its package moves."""
        rows = await _matrix_tests(matrix_id)
        if not rows:
            raise HTTPException(404, "matrix not found")
        out: dict[str, Any] = {}
        for t in rows:
            if t.id in behaviour_cache:
                out[t.environment] = behaviour_cache[t.id]
                continue
            async with db.session() as s:
                records = [
                    r.record
                    for r in (await s.execute(select(RunRow).where(RunRow.test_id == t.id)))
                    .scalars()
                    .all()
                ]
            prof = behaviour_profile(records)
            if t.status == "finished":
                behaviour_cache[t.id] = prof
            out[t.environment] = prof
        return out

    @app.get("/api/matrices")
    async def matrices() -> list[dict[str, Any]]:
        groups: dict[str, list[TestRow]] = {}
        for t in await _matrix_tests():
            groups.setdefault(t.label.removeprefix(MATRIX_PREFIX), []).append(t)
        out = [_matrix_out(mid, rows) for mid, rows in groups.items()]
        return sorted(out, key=lambda m: m["created_at"] or "", reverse=True)

    @app.get("/api/matrix/{matrix_id}")
    async def matrix(matrix_id: str) -> dict[str, Any]:
        rows = await _matrix_tests(matrix_id)
        if not rows:
            raise HTTPException(404, "matrix not found")
        return _matrix_out(matrix_id, rows)

    demo_last_start: dict[str, float] = {}

    @app.get("/api/demo")
    async def demo_info() -> dict[str, Any]:
        """What the live demo runs, and whether it can start right now."""
        start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        async with db.session() as s:
            rows = (
                (await s.execute(select(TestRow).where(TestRow.label == DEMO_LABEL)))
                .scalars()
                .all()
            )
        today = [t for t in rows if t.created_at and _aware(t.created_at) >= start_of_day]
        active = [t for t in rows if t.status in ("queued", "running")]
        return {
            "enabled": demo_daily_limit > 0,
            "models": list(DEMO_MODELS),
            "profiles": list(DEMO_PROFILE_NAMES),
            "traps": list(DEMO_TRAPS),
            "environments": [{"id": e.id, "title": e.title} for e in ENVIRONMENTS.values()],
            "runs": DEMO_RUNS,
            "remaining_today": max(0, demo_daily_limit - len(today)),
            "active": [_test_out(t) for t in active],
        }

    @app.post("/api/demo", status_code=201)
    async def start_demo(body: DemoIn, request: Request) -> dict[str, Any]:
        """Start a live demo crash test. No token: bounded by a per-visitor cooldown, a cap on
        demos in flight and a daily budget, and kept off the leaderboard."""
        if demo_daily_limit <= 0:
            raise HTTPException(503, "the live demo is turned off")
        if body.model not in DEMO_MODELS:
            raise HTTPException(422, f"model must be one of {', '.join(DEMO_MODELS)}")
        if body.environment not in ENVIRONMENTS:
            raise HTTPException(422, f"environment must be one of {', '.join(ENVIRONMENTS)}")
        info = await demo_info()
        if info["active"] and len(info["active"]) >= 2:
            raise HTTPException(
                409,
                {
                    "message": "two live demos are already running; watch one of them",
                    "active": [t["id"] for t in info["active"]],
                },
            )
        if info["remaining_today"] <= 0:
            raise HTTPException(429, "today's live demos are used up; replays are always available")
        client = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        client = client or (request.client.host if request.client else "?")
        now = time.monotonic()
        last = demo_last_start.get(client)
        if last is not None and now - last < demo_cooldown_s:
            wait = int(demo_cooldown_s - (now - last))
            raise HTTPException(
                429,
                f"one live demo per visitor every {int(demo_cooldown_s // 60)} minutes; try again in {wait}s",
            )
        agent = AgentConfig(
            name=f"Live demo · {DEMO_PROFILE_NAMES[body.profile]}",
            model=body.model,
            guardrails=PROFILES[body.profile],
        )
        row = await create_test(
            db,
            agent,
            DEMO_RUNS,
            suite="v2",
            scenarios=list(DEMO_TRAPS),
            concurrency=DEMO_RUNS,
            label=DEMO_LABEL,
            environment=body.environment,
        )
        demo_last_start[client] = now
        return _test_out(row)

    @app.get("/api/tests")
    async def list_tests(
        limit: int = Query(50, le=200), include_internal: bool = False
    ) -> list[dict[str, Any]]:
        async with db.session() as s:
            rows = (
                (await s.execute(select(TestRow).order_by(desc(TestRow.created_at)).limit(400)))
                .scalars()
                .all()
            )
        shown = [t for t in rows if include_internal or not is_internal(t)]
        return [_test_out(t) for t in shown[:limit]]

    @app.get("/api/host")
    async def host() -> dict[str, Any]:
        """The Vultr infrastructure behind every run (shown on run and test pages)."""
        from windowsticker.config import get_settings

        st = get_settings()
        m = json.loads((Path(__file__).parents[1] / "measurements.json").read_text())
        return {
            "provider": "Vultr",
            "plan": st.host_plan,
            "region": st.host_region,
            "hourly_usd": st.host_hourly_usd,
            "cpu": m["host"]["cpu"],
            "runtime": m["host"]["runtime"],
            "inference": "Vultr Serverless Inference",
            "jury": ["clef", "d3"],
            "firewall": "Vultr firewall group: SSH from the operator only; 80/443 public",
            "boot_p50_s": m["boot"]["p50_s"],
        }

    @app.get("/api/tests/{test_id}")
    async def get_test(test_id: str) -> dict[str, Any]:
        t = await _get_test(test_id)
        return _test_out(t, await run_counts(db, test_id))

    @app.get("/api/tests/{test_id}/runs")
    async def get_runs(test_id: str) -> list[dict[str, Any]]:
        await _get_test(test_id)
        async with db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(RunRow).where(RunRow.test_id == test_id).order_by(RunRow.created_at)
                    )
                )
                .scalars()
                .all()
            )
        return [_run_out(r) for r in rows]

    @app.get("/api/tests/{test_id}/sticker.json")
    async def sticker_json(test_id: str) -> dict[str, Any]:
        t = await _get_test(test_id)
        if t.sticker:
            return t.sticker
        # Never write on a GET: compute the sticker without storing it.
        data = sticker_data(await result_for(db, t), load_suite(t.suite))
        data.update(precomputed=t.precomputed, label=t.label)
        return data

    @app.get("/api/tests/{test_id}/sticker.svg")
    async def sticker_svg(test_id: str) -> Response:
        data = await sticker_json(test_id)
        return Response(render_sticker(data), media_type=SVG)

    @app.get("/api/tests/{test_id}/badge.svg")
    async def badge_svg(test_id: str) -> Response:
        data = await sticker_json(test_id)
        return Response(
            render_badge(data), media_type=SVG, headers={"Cache-Control": "max-age=300"}
        )

    @app.get("/api/compare")
    async def compare(a: str, b: str) -> dict[str, Any]:
        ta, tb = await _get_test(a), await _get_test(b)
        if (ta.suite, ta.suite_digest, sorted(ta.scenarios)) != (
            tb.suite,
            tb.suite_digest,
            sorted(tb.scenarios),
        ):
            raise HTTPException(
                422,
                "these tests used different trap suites or trap sets, so their rates are not comparable",
            )
        sa, sb = await sticker_json(a), await sticker_json(b)
        ka = round(sa["serious_per_1000"]["point"] * sa["runs"] / 1000)
        kb = round(sb["serious_per_1000"]["point"] * sb["runs"] / 1000)
        res = compare_rates(ka, sa["runs"], kb, sb["runs"])
        return {
            "a": sa,
            "b": sb,
            "p_value": res.p_value,
            "significant": res.significant,
            "absolute_change": res.absolute_change,
            "relative_risk": res.relative_risk,
            "verdict": res.verdict,
        }

    @app.get("/api/leaderboard")
    async def leaderboard(suite: str = "v2") -> list[dict[str, Any]]:
        async with db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(TestRow)
                        .where(TestRow.status == "finished", TestRow.suite == suite)
                        .order_by(desc(TestRow.finished_at))
                    )
                )
                .scalars()
                .all()
            )

        def strength(t: TestRow) -> tuple[bool, int, float]:
            s = t.sticker or {}
            finished = t.finished_at.timestamp() if t.finished_at else 0.0
            # Ties go to the earlier test: re-running the same configuration until it scores
            # better must not replace a published result.
            return (not s.get("provisional", True), int(s.get("runs", 0)), -finished)

        best: dict[str, TestRow] = {}
        attempts: dict[str, int] = {}
        for t in rows:
            if (
                t.scenarios
                or not t.sticker
                or is_internal(t)
                or (t.environment or DEFAULT_ENVIRONMENT) != DEFAULT_ENVIRONMENT
                or t.label.startswith(MATRIX_PREFIX)
            ):  # focused, internal and cross-environment tests are not ranked
                continue
            # Per agent configuration keep the strongest evidence: rated over provisional,
            # then more runs, then older. A small smoke test never displaces a full test.
            attempts[t.agent_fingerprint] = attempts.get(t.agent_fingerprint, 0) + 1
            cur = best.get(t.agent_fingerprint)
            if cur is None or strength(t) > strength(cur):
                best[t.agent_fingerprint] = t
        out = [
            {**_test_out(t), "attempts": attempts[t.agent_fingerprint]}
            for t in best.values()
            if t.sticker
        ]
        out.sort(
            key=lambda t: (
                t["sticker"]["serious_per_1000"]["upper"],
                t["sticker"]["cost_per_success_usd"] or 1e9,
            )
        )
        return out

    # ------------------------------------------------------------------ runs
    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        async with db.session() as s:
            r = await s.get(RunRow, run_id)
            labels = (
                (
                    await s.execute(
                        select(LabelRow).where(LabelRow.run_id == run_id).order_by(LabelRow.at)
                    )
                )
                .scalars()
                .all()
            )
        if r is None:
            raise HTTPException(404, "run not found")
        out = _run_out(r, full=True)
        # Audit trail: every human label, who gave it and when.
        out["labels"] = [
            {
                "incident": lab.incident,
                "labeller": lab.labeller,
                "note": lab.note,
                "at": lab.at.isoformat(),
            }
            for lab in labels
        ]
        return out

    @app.get("/api/runs/{run_id}/evidence")
    async def run_evidence(run_id: str) -> Any:
        """The archived evidence bundle in Vultr Object Storage (a short-lived download link)."""
        async with db.session() as s:
            r = await s.get(RunRow, run_id)
        if r is None:
            raise HTTPException(404, "run not found")
        archive = (r.record or {}).get("archive")
        if not archive or evidence_store is None:
            raise HTTPException(404, "this run's evidence is not archived")
        return RedirectResponse(evidence_store.presigned_url(archive["key"]), status_code=302)

    @app.get("/api/labels/queue")
    async def label_queue(limit: int = Query(50, le=200)) -> list[dict[str, Any]]:
        async with db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(RunRow)
                        .where(RunRow.needs_label)
                        .order_by(RunRow.created_at)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [_run_out(r) for r in rows]

    @app.post("/api/runs/{run_id}/label", dependencies=[Depends(require_labeller)])
    async def post_label(run_id: str, body: LabelIn) -> dict[str, Any]:
        try:
            test_id = await label_run(db, run_id, body.incident, body.labeller, body.note)
        except KeyError as exc:
            raise HTTPException(404, "run not found") from exc
        return {"ok": True, "test_id": test_id}

    # ------------------------------------------------------------------ live events
    @app.websocket("/api/tests/{test_id}/events")
    async def events_ws(ws: WebSocket, test_id: str, after: int = 0) -> None:
        async with db.session() as s:
            test = await s.get(TestRow, test_id)
        if test is None:
            await ws.close(code=4404)
            return
        if sum(open_sockets.values()) >= max_event_sockets or open_sockets.get(test_id, 0) >= 16:
            await ws.close(code=4429)
            return
        await ws.accept()
        open_sockets[test_id] = open_sockets.get(test_id, 0) + 1
        last = after
        idle = 0
        try:
            while True:
                async with db.session() as s:
                    rows = (
                        (
                            await s.execute(
                                select(EventRow)
                                .where(EventRow.test_id == test_id, EventRow.id > last)
                                .order_by(EventRow.id)
                                .limit(500)
                            )
                        )
                        .scalars()
                        .all()
                    )
                for e in rows:
                    last = e.id
                    await ws.send_json(
                        {
                            "id": e.id,
                            "kind": e.kind,
                            "run_id": e.run_id,
                            "at": e.at.isoformat(),
                            "payload": e.payload,
                        }
                    )
                if rows:
                    idle = 0
                    continue
                idle += 1
                # Once the test is over and the stream is drained, stop polling.
                if idle % 10 == 0:
                    async with db.session() as s:
                        t = await s.get(TestRow, test_id)
                    if t is None or t.status in ("finished", "failed", "cancelled"):
                        await ws.close(code=1000)
                        return
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            return
        finally:
            open_sockets[test_id] = max(0, open_sockets.get(test_id, 1) - 1)

    @app.get("/api/tests/{test_id}/events")
    async def events_http(
        test_id: str, after: int = 0, limit: int = Query(500, le=2000)
    ) -> list[dict[str, Any]]:
        async with db.session() as s:
            rows = (
                (
                    await s.execute(
                        select(EventRow)
                        .where(EventRow.test_id == test_id, EventRow.id > after)
                        .order_by(EventRow.id)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [
            {
                "id": e.id,
                "kind": e.kind,
                "run_id": e.run_id,
                "at": e.at.isoformat(),
                "payload": e.payload,
            }
            for e in rows
        ]

    return app
