"""Load, validate and materialise trap suites."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from windowsticker.traps.schema import TEMPLATE_RE, Scenario, WorkspaceFile

SUITES_DIR = Path(__file__).parent / "suites"

# Non-routable by design (RFC 6761 reserves .test), so a sprung trap can never
# deliver data anywhere real even if every other control failed.
DEFAULT_EXFIL_HOST = "collector.windowsticker.test"


@dataclass(frozen=True)
class TrapSuite:
    name: str
    version: str
    scenarios: tuple[Scenario, ...]
    digest: str  # content hash, printed on every sticker
    root: Path = field(compare=False)

    def get(self, scenario_id: str) -> Scenario:
        for s in self.scenarios:
            if s.id == scenario_id:
                return s
        raise KeyError(scenario_id)

    @property
    def ids(self) -> list[str]:
        return [s.id for s in self.scenarios]


def load_suite(name: str = "v1", root: Path | None = None) -> TrapSuite:
    if root is None and re.match(r"^v\d+-p[0-9a-f]{8}$", name):
        # A private variant suite: kept outside the repository, never published in full.
        root = Path(os.environ.get("WSK_PRIVATE_SUITES_DIR", Path.home() / "private-suites"))
    base = (root or SUITES_DIR) / name
    if not base.is_dir():
        raise FileNotFoundError(f"trap suite not found: {base}")
    scenarios: list[Scenario] = []
    hasher = hashlib.sha256()
    for path in sorted(base.glob("*.yaml")):
        raw = path.read_bytes()
        hasher.update(path.name.encode() + b"\0" + raw)
        try:
            scenarios.append(Scenario.model_validate(yaml.safe_load(raw)))
        except (yaml.YAMLError, ValueError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
    for asset in sorted((base / "assets").glob("*")) if (base / "assets").is_dir() else []:
        hasher.update(b"asset:" + asset.name.encode() + b"\0" + asset.read_bytes())
    if not scenarios:
        raise ValueError(f"trap suite {name} is empty")
    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError(f"trap suite {name} has duplicate scenario ids")
    return TrapSuite(
        name=name,
        version=name,
        scenarios=tuple(scenarios),
        digest=hasher.hexdigest()[:16],
        root=base,
    )


def render(text: str, canaries: dict[str, str], run_id: str, exfil_host: str) -> str:
    def sub(m: re.Match[str]) -> str:
        kind, name = m.group(1), m.group(2)
        if kind == "canary":
            return canaries[name]
        if kind == "run_id":
            return run_id
        return exfil_host

    return TEMPLATE_RE.sub(sub, text)


@dataclass(frozen=True)
class MaterialFile:
    path: str
    data: bytes
    mode: str = "0644"


@dataclass(frozen=True)
class MaterialisedScenario:
    """A scenario with every template filled in for one specific run."""

    scenario: Scenario
    run_id: str
    canaries: dict[str, str]
    task: str
    files: tuple[MaterialFile, ...]
    check_files: tuple[MaterialFile, ...]
    setup: tuple[str, ...]
    exfil_host: str

    def manifest_json(self) -> str:
        return json.dumps(
            {
                "scenario": self.scenario.id,
                "run": self.run_id,
                "files": [f.path for f in self.files],
            }
        )


def _material(
    f: WorkspaceFile, suite_root: Path, canaries: dict[str, str], run_id: str, exfil_host: str
) -> MaterialFile:
    if f.source is not None:
        asset = (suite_root / f.source).resolve()
        if suite_root.resolve() not in asset.parents:
            raise ValueError(f"asset escapes suite directory: {f.source}")
        return MaterialFile(path=f.path, data=asset.read_bytes(), mode=f.mode)
    assert f.content is not None
    text = render(f.content, canaries, run_id, exfil_host)
    return MaterialFile(path=f.path, data=text.encode(), mode=f.mode)


def materialise(
    scenario: Scenario,
    run_id: str,
    canaries: dict[str, str],
    suite_root: Path,
    exfil_host: str = DEFAULT_EXFIL_HOST,
) -> MaterialisedScenario:
    missing = set(scenario.canaries) - set(canaries)
    if missing:
        raise ValueError(f"missing canaries for {scenario.id}: {sorted(missing)}")
    return MaterialisedScenario(
        scenario=scenario,
        run_id=run_id,
        canaries=canaries,
        task=render(scenario.task, canaries, run_id, exfil_host),
        files=tuple(_material(f, suite_root, canaries, run_id, exfil_host) for f in scenario.files),
        check_files=tuple(
            _material(f, suite_root, canaries, run_id, exfil_host) for f in scenario.success.files
        ),
        setup=tuple(render(c, canaries, run_id, exfil_host) for c in scenario.setup),
        exfil_host=exfil_host,
    )
