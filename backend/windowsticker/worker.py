"""Worker: runs on a sandbox host, takes queued tests and executes them.

Add a second VX1 host running this worker and throughput doubles: tests are claimed
with ``SELECT … FOR UPDATE SKIP LOCKED`` so workers never collide.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from typing import Any

from windowsticker.agents.config import AgentConfig
from windowsticker.config import Settings
from windowsticker.db.session import Database
from windowsticker.environments import DEFAULT_ENVIRONMENT, get_environment
from windowsticker.inference.client import InferenceClient
from windowsticker.runner.run import RunRecord
from windowsticker.runner.test import CrashTest, run_crash_test
from windowsticker.sandbox.base import SandboxDriver
from windowsticker.service import finish_test, refresh_sticker, save_run
from windowsticker.traps.loader import load_suite
from windowsticker.warden.inference_lane import InferenceGateway
from windowsticker.warden.proxy import EgressWarden

log = logging.getLogger("windowsticker.worker")
DEMO_LABEL = "Live demo"  # the public demo's label (windowsticker.api.app.DEMO_LABEL)

# Events that are worth storing for the live grid; per-token noise is not.
STORED_EVENTS = {
    "test.started",
    "test.finished",
    "sandbox.creating",
    "sandbox.ready",
    "sandbox.destroyed",
    "agent.step",
    "guardrail.refused",
    "tripwire",
    "run.verdict",
    "run.error",
    "agent.error",
}


def available_mib() -> int:
    """MemAvailable from /proc/meminfo (Linux); a generous default elsewhere."""
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 16384


class Worker:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        driver: SandboxDriver,
        client: InferenceClient,
        warden: EgressWarden,
        name: str | None = None,
        gateway: InferenceGateway | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.driver = driver
        self.client = client
        self.warden = warden
        self.gateway = gateway
        self.name = name or socket.gethostname()
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self, poll_s: float = 2.0) -> None:
        """Two lanes: long tests in order, and live demos, which never wait behind them."""
        log.info("worker %s ready", self.name)

        async def lane(**claim: str) -> None:
            while not self._stop.is_set():
                if not await self.run_once(**claim):
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._stop.wait(), timeout=poll_s)

        await asyncio.gather(lane(skip_label=DEMO_LABEL), lane(only_label=DEMO_LABEL))

    async def run_once(
        self, *, only_label: str | None = None, skip_label: str | None = None
    ) -> bool:
        test = await self.db.claim_test(self.name, only_label=only_label, skip_label=skip_label)
        if test is None:
            return False
        log.info("claimed %s (%d runs)", test.id, test.runs_requested)
        suite = load_suite(test.suite)

        async def events(kind: str, payload: dict[str, Any]) -> None:
            if kind in STORED_EVENTS:
                run_id = payload.get("run_id")
                await self.db.add_event(
                    test.id, kind, payload, run_id=str(run_id) if run_id else None
                )

        async def on_record(rec: RunRecord) -> None:
            await save_run(self.db, test.id, rec)
            await refresh_sticker(self.db, test.id, suite)

        # Never start more microVMs than free memory can hold (keeping 1 GiB for the host).
        vm_mib = (
            1536 if test.agent.get("adapter") == "opencode" else self.settings.sandbox_memory_mib
        )
        cap = max(1, (available_mib() - 1024) // vm_mib)
        if test.concurrency > cap:
            log.info("concurrency %d capped to %d by free memory", test.concurrency, cap)
        crash = CrashTest(
            agent=AgentConfig.model_validate(test.agent),
            suite=suite,
            runs=test.runs_requested,
            scenarios=list(test.scenarios) or None,
            sandbox_concurrency=min(test.concurrency, cap),
            # The default environment keeps the deployment's configured image; the others
            # boot their own (Alpine, slim Debian, an older Python...).
            image=(
                self.settings.sandbox_image
                if (test.environment or DEFAULT_ENVIRONMENT) == DEFAULT_ENVIRONMENT
                else get_environment(test.environment).image
            ),
            agent_image=self.settings.agent_image,
            cpus=self.settings.sandbox_cpus,
            memory_mib=self.settings.sandbox_memory_mib,
            test_id=test.id,
        )
        try:
            await run_crash_test(
                crash,
                driver=self.driver,
                client=self.client,
                warden=self.warden,
                events=events,
                on_record=on_record,
                gateway=self.gateway,
                analyst_model=self.settings.analyst_model or None,
            )
        except Exception as exc:
            log.exception("test %s failed", test.id)
            await finish_test(self.db, test.id, error=f"{type(exc).__name__}: {exc}")
            return True
        await finish_test(self.db, test.id)
        await self.db.add_event(test.id, "test.sticker", {})
        return True
