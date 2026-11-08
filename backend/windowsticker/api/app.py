"""HTTP + WebSocket API for the web app, the CLI and the GitHub Action."""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

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
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from windowsticker import __version__
from windowsticker.agents.config import AgentConfig
from windowsticker.agents.guardrails import PROFILES, GuardrailEngine
from windowsticker.db.models import EventRow, LabelRow, RunRow, TestRow
from windowsticker.db.session import Database
from windowsticker.service import create_test, is_internal, label_run, result_for, run_counts
from windowsticker.stats.ab import compare_rates
from windowsticker.stats.rating import MIN_TRIALS_FOR_RATING, THRESHOLDS, runs_needed_for
from windowsticker.sticker.render import render_badge, render_sticker, sticker_data
from windowsticker.traps.loader import load_suite

SVG = "image/svg+xml"


class CreateTest(BaseModel):
    agent: AgentConfig
    runs: int = Field(36, ge=1, le=1000)
    suite: str = "v2"
    scenarios: list[str] = Field(default_factory=list)
    concurrency: int = Field(8, ge=1, le=16)
    label: str = ""


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
        return {
            "name": s.name,
            "digest": s.digest,
            "scenarios": [
                {
                    "id": sc.id,
                    "title": sc.title,
                    "category": sc.category.value,
                    "severity": sc.severity.value,
                    "summary": sc.summary,
                    "task": sc.task,
                    "tripwires": [t.model_dump(mode="json") for t in sc.tripwires],
                    "tags": sc.tags,
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

    @app.get("/api/escape-matrix")
    async def escape_matrix(profile: str = "reference") -> dict[str, Any]:
        """Measured escape matrix for a sandbox profile: reference, or agent (in-VM agent)."""
        name = {"reference": "escape_matrix.json", "agent": "escape_matrix_agent.json"}.get(profile)
        if name is None:
            raise HTTPException(404, "unknown profile")
        data: dict[str, Any] = json.loads((Path(__file__).parents[1] / name).read_text())
        return data

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
            return (not s.get("provisional", True), int(s.get("runs", 0)), finished)

        best: dict[str, TestRow] = {}
        for t in rows:
            if (
                t.scenarios or not t.sticker or is_internal(t)
            ):  # focused/internal tests are not ranked
                continue
            # Per agent configuration keep the strongest evidence: rated over provisional,
            # then more runs, then newer. A small smoke test never displaces a full test.
            cur = best.get(t.agent_fingerprint)
            if cur is None or strength(t) > strength(cur):
                best[t.agent_fingerprint] = t
        out = [_test_out(t) for t in best.values() if t.sticker]
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
