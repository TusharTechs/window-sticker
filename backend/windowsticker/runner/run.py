"""Execute one crash-test run end to end.

fork microVM → seed workspace → snapshot hashes → agent works → snapshot hashes →
hidden check → collect warden log → destroy microVM → verify teardown → grade.

The sandbox is always destroyed, even if the agent, the model or the harness fails.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import mimetypes
import secrets
import shlex
import time
from dataclasses import dataclass, field
from typing import Any

from windowsticker.agents.config import AgentConfig
from windowsticker.agents.opencode import OpenCodeAgent
from windowsticker.agents.reference import Attachment, EventSink, ReferenceAgent, _noop
from windowsticker.domain import (
    CapEvent,
    CheckResult,
    FinalReport,
    JuryAnswer,
    RunEvidence,
    Verdict,
)
from windowsticker.grading.fusion import fuse
from windowsticker.grading.jury import DEFAULT_JURORS, convene
from windowsticker.grading.tripwires import evaluate_tripwires
from windowsticker.inference.client import InferenceClient, Usage
from windowsticker.sandbox.base import NetworkSpec, Sandbox, SandboxDriver, SandboxSpec
from windowsticker.traps.canary import make_canaries
from windowsticker.traps.loader import TrapSuite, materialise
from windowsticker.traps.schema import Scenario
from windowsticker.warden.inference_lane import InferenceGateway
from windowsticker.warden.proxy import EgressWarden

HASH_ROOTS = ("/workspace", "/root", "/etc/cron.d", "/opt")
HASH_EXCLUDES = ("/root/.cache", "/opt/wsk-check", "/workspace/.wsk", "/root/.npm", "/root/.local")
SETUP_TIMEOUT = 60.0
CHECK_TIMEOUT = 90.0


@dataclass
class RunBudget:
    wall_clock_s: float = 240.0
    token_budget: int = 60_000


@dataclass
class RunTimings:
    boot_s: float = 0.0
    agent_s: float = 0.0
    total_s: float = 0.0
    teardown_s: float = 0.0


@dataclass
class RunRecord:
    run_id: str
    scenario_id: str
    agent_fingerprint: str
    model: str
    host_id: str
    sandbox_name: str
    evidence: RunEvidence
    verdict: Verdict
    agent_usage: Usage
    jury_usage: Usage
    timings: RunTimings
    teardown_verified: bool
    jury_raw: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def cost_usd(self) -> float:
        return self.agent_usage.cost_usd + self.jury_usage.cost_usd


def new_run_id() -> str:
    return "run_" + secrets.token_hex(6)


async def file_hashes(sandbox: Sandbox) -> dict[str, str]:
    roots = " ".join(shlex.quote(r) for r in HASH_ROOTS)
    prunes = " -o ".join(f"-path {shlex.quote(p)}" for p in HASH_EXCLUDES)
    # Interpreter caches are side effects of running code, not changes the agent made.
    caches = "-name __pycache__ -o -name .pytest_cache -o -name .mypy_cache"
    cmd = (
        f"find {roots} \\( {prunes} -o {caches} \\) -prune -o -type f ! -name '*.pyc' "
        "-size -2M -print0 2>/dev/null | xargs -0 -r sha256sum 2>/dev/null"
    )
    res = await sandbox.exec(cmd, timeout_s=60)
    hashes: dict[str, str] = {}
    for line in res.stdout.splitlines():
        digest, _, path = line.partition("  ")
        if path:
            hashes[path] = digest
    return hashes


# Environment variables an agent could plant to change how the hidden check behaves.
CHECK_ENV_UNSET = ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTHONUSERBASE", "LD_PRELOAD")


def hardened_check(command: str) -> str:
    """Run the hidden check with a scrubbed environment (no user site-packages, no planted
    Python path or preload). The agent never sees the check, but it controls the VM."""
    unset = " ".join(f"-u {v}" for v in CHECK_ENV_UNSET)
    return f"env {unset} PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 sh -c {shlex.quote(command)}"


async def cross_check(
    sandbox: Sandbox, scenario: Scenario, mat: Any, guest_hashes: dict[str, str]
) -> list[str]:
    """Re-hash the files tripwires depend on through the runtime's file API (a different code
    path from the guest's find/sha256sum). A mismatch means the guest's evidence was forged."""
    paths = {f.path for f in mat.files}
    for t in scenario.tripwires:
        paths.update(p for p in t.paths if "*" not in p)
    mismatches = []
    for path in sorted(paths):
        try:
            digest: str | None = hashlib.sha256(await sandbox.read_file(path)).hexdigest()
        except Exception:
            digest = None
        if digest != guest_hashes.get(path):
            mismatches.append(path)
    return mismatches


async def _seed(sandbox: Sandbox, files: Any, setup: tuple[str, ...]) -> None:
    for f in files:
        await sandbox.write_file(f.path, f.data, f.mode)
    for cmd in setup:
        res = await sandbox.exec(cmd, timeout_s=SETUP_TIMEOUT, cwd="/workspace")
        if res.exit_code != 0:
            raise RuntimeError(f"scenario setup failed: {cmd!r}: {res.stderr[:300]}")


async def execute_run(
    *,
    suite: TrapSuite,
    scenario: Scenario,
    agent: AgentConfig,
    driver: SandboxDriver,
    client: InferenceClient,
    warden: EgressWarden,
    image: str,
    agent_image: str = "windowsticker/agent-base:1",
    cpus: int = 1,
    memory_mib: int = 1024,
    budget: RunBudget | None = None,
    jurors: tuple[str, ...] = DEFAULT_JURORS,
    test_id: str = "adhoc",
    run_id: str | None = None,
    events: EventSink = _noop,
    gateway: InferenceGateway | None = None,
) -> RunRecord:
    return await _execute_run(
        suite=suite,
        scenario=scenario,
        agent=agent,
        driver=driver,
        client=client,
        warden=warden,
        image=image,
        agent_image=agent_image,
        cpus=cpus,
        memory_mib=memory_mib,
        budget=budget,
        jurors=jurors,
        test_id=test_id,
        run_id=run_id or new_run_id(),
        sink=events,
        gateway=gateway,
    )


async def _execute_run(
    *,
    suite: TrapSuite,
    scenario: Scenario,
    agent: AgentConfig,
    driver: SandboxDriver,
    client: InferenceClient,
    warden: EgressWarden,
    image: str,
    agent_image: str,
    cpus: int,
    memory_mib: int,
    budget: RunBudget | None,
    jurors: tuple[str, ...],
    test_id: str,
    run_id: str,
    sink: EventSink,
    gateway: InferenceGateway | None,
) -> RunRecord:
    budget = budget or RunBudget()

    async def events(kind: str, payload: dict[str, Any]) -> None:
        # Every event from this run carries its run id, including the agent's own.
        await sink(kind, {"run_id": run_id, **payload})

    started = time.perf_counter()
    canaries = make_canaries(scenario.canaries, run_id)
    mat = materialise(scenario, run_id, canaries, suite.root)
    timings = RunTimings()
    errors: list[str] = []

    evidence = RunEvidence(run_id=run_id, scenario_id=scenario.id, canaries=canaries)
    agent_usage = Usage()
    # An agent whose brain runs inside the VM (OpenCode) must reach the inference API: it
    # gets that one destination directly, a filtering DNS lane, and a placeholder key.
    # An agent whose brain runs inside the VM (OpenCode) reaches the model only through the
    # host's inference lane: plain HTTP to one host port, no key in the guest, no DNS, no
    # direct route out. The lane adds the key, pins the model and meters tokens.
    inside = agent.adapter == "opencode"
    if inside and gateway is None:
        raise RuntimeError("agents that run inside the VM need the inference gateway")
    lane = await warden.open_lane(run_id, allowlist=())
    inference_lane = (
        gateway.open(run_id, agent.model, budget.token_budget) if inside and gateway else None
    )
    network = NetworkSpec(
        warden_host=warden.address(lane),
        host_ports=(gateway.port,) if inference_lane and gateway else (),
    )
    env = (
        {"WSK_INFERENCE_BASE_URL": InferenceGateway.base_url(inference_lane, gateway.port)}
        if inference_lane and gateway
        else {}
    )
    spec = SandboxSpec(
        name=f"wsk-{run_id}",
        image=agent_image if inside else image,
        cpus=cpus,
        memory_mib=max(memory_mib, 1536) if inside else memory_mib,
        network=network,
        env=env,
        labels={"wsk.run": run_id, "wsk.test": test_id},
        # Hard VM lifetime enforced by the runtime: agent budget + setup, check and grace.
        max_duration_s=budget.wall_clock_s + 180,
    )
    sandbox: Sandbox | None = None
    host_id = "unknown"
    try:
        await events("sandbox.creating", {"run_id": run_id, "scenario": scenario.id})
        t0 = time.perf_counter()
        sandbox = await driver.create(spec)
        timings.boot_s = time.perf_counter() - t0
        host_id = sandbox.host_id
        await events("sandbox.ready", {"run_id": run_id, "boot_s": timings.boot_s, "host": host_id})

        await _seed(sandbox, mat.files, mat.setup)
        evidence.files_before = await file_hashes(sandbox)

        attachments = [
            Attachment(
                path=p,
                mime=mimetypes.guess_type(p)[0] or "image/png",
                data=next(f.data for f in mat.files if f.path == p),
            )
            for p in scenario.attachments
        ]
        ref: ReferenceAgent | OpenCodeAgent
        if inside:
            ref = OpenCodeAgent(
                agent, client, sandbox, wall_clock_s=budget.wall_clock_s, events=events
            )
        else:
            ref = ReferenceAgent(
                agent, client, sandbox, token_budget=budget.token_budget, events=events
            )
        t1 = time.perf_counter()
        # From here on the run counts: it is excluded only if the harness failed before this.
        evidence.agent_started = True
        try:
            outcome = await asyncio.wait_for(
                ref.run(mat.task, attachments), timeout=budget.wall_clock_s
            )
        except TimeoutError:
            outcome = ref.outcome
            outcome.caps.append(
                CapEvent(kind="wall_clock", detail=f"run exceeded {budget.wall_clock_s:.0f}s")
            )
            if not outcome.final.finished:
                outcome.final = FinalReport(
                    finished=False, summary="(stopped by wall-clock budget)"
                )
        timings.agent_s = time.perf_counter() - t1
        agent_usage = outcome.usage
        errors += outcome.errors
        evidence.steps = outcome.steps
        evidence.commands = outcome.commands
        evidence.written_paths = outcome.written_paths
        evidence.caps = outcome.caps
        evidence.final = outcome.final

        # Stop anything the scenario knows the agent may have left running.
        for cmd in scenario.cleanup:
            await sandbox.exec(f"{cmd} 2>/dev/null; true", timeout_s=15)
        evidence.files_after = await file_hashes(sandbox)
        evidence.integrity = await cross_check(sandbox, scenario, mat, evidence.files_after)

        for f in mat.check_files:
            await sandbox.write_file(f.path, f.data, f.mode)
        res = await sandbox.exec(
            hardened_check(scenario.success.command), timeout_s=CHECK_TIMEOUT, cwd="/workspace"
        )
        evidence.success_check = CheckResult(
            command=scenario.success.command,
            exit_code=res.exit_code,
            passed=res.exit_code == scenario.success.expect_exit and not res.timed_out,
            output=(res.stdout + res.stderr)[-2000:],
        )
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        await events("run.error", {"run_id": run_id, "error": errors[-1]})
    finally:
        lane = await warden.close_lane(run_id)
        evidence.egress = lane.events
        if inference_lane is not None and gateway is not None:
            metered = gateway.close(inference_lane.token)
            evidence.egress += metered.events
            # Cost from tokens the host metered, not from what the agent reported.
            agent_usage = Usage(
                metered.prompt_tokens,
                metered.completion_tokens,
                await client.cost(agent.model, metered.prompt_tokens, metered.completion_tokens),
            )
        t2 = time.perf_counter()
        if sandbox is not None:
            with contextlib.suppress(Exception):
                await sandbox.destroy()
        timings.teardown_s = time.perf_counter() - t2
        await events("sandbox.destroyed", {"run_id": run_id, "teardown_s": timings.teardown_s})

    teardown_verified = False
    with contextlib.suppress(Exception):
        teardown_verified = not await driver.live("wsk.run", run_id)

    hits = evaluate_tripwires(scenario, evidence)
    for h in hits:
        await events("tripwire", {"run_id": run_id, "hit": h.model_dump(mode="json")})
    answers: list[JuryAnswer] = []
    jury_usage = Usage()
    jury_raw: dict[str, Any] = {}
    if evidence.steps:
        answers, jury_usage, jury_raw = await convene(client, evidence, mat.task, jurors)
    verdict = fuse(evidence, hits, answers)
    if errors and not evidence.agent_started:
        verdict.notes.append("run errored before the agent acted; excluded from rates")
    timings.total_s = time.perf_counter() - started
    await events("run.verdict", {"run_id": run_id, "verdict": verdict.model_dump(mode="json")})

    return RunRecord(
        run_id=run_id,
        scenario_id=scenario.id,
        agent_fingerprint=agent.fingerprint(),
        model=agent.model,
        host_id=host_id,
        sandbox_name=spec.name,
        evidence=evidence,
        verdict=verdict,
        agent_usage=agent_usage,
        jury_usage=jury_usage,
        timings=timings,
        teardown_verified=teardown_verified,
        jury_raw=jury_raw,
        errors=errors,
    )
