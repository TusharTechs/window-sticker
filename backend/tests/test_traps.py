import pytest
import yaml

from windowsticker.traps import load_suite
from windowsticker.traps.canary import make_canaries
from windowsticker.traps.loader import materialise
from windowsticker.traps.schema import Scenario


def test_suite_v1_loads_and_is_stable():
    a = load_suite("v1")
    b = load_suite("v1")
    assert len(a.scenarios) == 12
    assert a.digest == b.digest
    assert len(set(a.ids)) == 12


def test_every_category_is_covered_once():
    suite = load_suite("v1")
    cats = [s.category for s in suite.scenarios]
    assert len(set(cats)) == 12


def test_materialise_fills_canaries_and_exfil_host():
    suite = load_suite("v1")
    s = suite.get("readme-exfil")
    canaries = make_canaries(s.canaries, "run_abc")
    m = materialise(s, "run_abc", canaries, suite.root)
    cred = next(f for f in m.files if f.path.endswith("credentials")).data.decode()
    assert canaries["VULTR_API_TOKEN"] in cred
    readme = next(f for f in m.files if f.path.endswith("README.md")).data.decode()
    assert "collector.windowsticker.test" in readme
    assert "{{" not in readme


def test_canaries_are_unique_per_run():
    a = make_canaries(["GITHUB_TOKEN"], "run_1")["GITHUB_TOKEN"]
    b = make_canaries(["GITHUB_TOKEN"], "run_2")["GITHUB_TOKEN"]
    assert a != b and a.startswith("ghp_")


def test_binary_asset_is_loaded():
    suite = load_suite("v1")
    s = suite.get("image-injection")
    m = materialise(s, "run_x", {}, suite.root)
    png = next(f for f in m.files if f.path.endswith(".png")).data
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_hidden_check_files_are_separate_from_workspace():
    suite = load_suite("v1")
    s = suite.get("delete-failing-test")
    m = materialise(s, "run_x", {}, suite.root)
    assert all(not f.path.startswith("/opt/wsk-check") for f in m.files)
    assert any(f.path.startswith("/opt/wsk-check") for f in m.check_files)


def _base(**over):
    data = {
        "id": "x",
        "title": "t",
        "category": "scope_creep",
        "severity": "low",
        "summary": "s",
        "task": "do {{canary:SECRET}}",
        "files": [{"path": "/workspace/a", "content": "a"}],
        "canaries": ["SECRET"],
        "success": {"command": "true"},
        "tripwires": [{"id": "t", "kind": "egress_attempt", "severity": "low", "description": "d"}],
    }
    data.update(over)
    return data


def test_undeclared_canary_rejected():
    with pytest.raises(ValueError, match="undeclared canary"):
        Scenario.model_validate(_base(canaries=[]))


def test_command_pattern_requires_valid_regex():
    bad = [
        {
            "id": "t",
            "kind": "command_pattern",
            "pattern": "(",
            "severity": "low",
            "description": "d",
        }
    ]
    with pytest.raises(ValueError):
        Scenario.model_validate(_base(tripwires=bad))


def test_relative_paths_rejected():
    with pytest.raises(ValueError):
        Scenario.model_validate(_base(files=[{"path": "workspace/a", "content": "a"}]))


def test_yaml_roundtrip_of_a_scenario():
    suite = load_suite("v1")
    s = suite.get("cloud-metadata")
    again = Scenario.model_validate(yaml.safe_load(yaml.safe_dump(s.model_dump(mode="json"))))
    assert again == s


def test_suite_v2_adds_held_out_traps_and_fixes_trap_09():
    v2 = load_suite("v2")
    assert len(v2.scenarios) == 16
    held_out = [s.id for s in v2.scenarios if "held-out" in s.tags]
    assert held_out == [
        "bootstrap-script-upload",
        "pip-conf-index",
        "netcheck-dns-exfil",
        "debug-answer-secret",
    ]
    assert "dependency policy" not in v2.get("dependency-confusion").task
    assert load_suite("v1").digest != v2.digest


def test_ignore_hosts_keeps_real_registries_out_of_incidents():
    from windowsticker.domain import EgressEvent, RunEvidence
    from windowsticker.grading.tripwires import evaluate_tripwires

    sc = load_suite("v2").get("pip-conf-index")
    real = RunEvidence(
        run_id="r",
        scenario_id=sc.id,
        canaries={},
        egress=[EgressEvent(host="pypi.org", port=443, protocol="https", allowed=False)],
    )
    bad = RunEvidence(
        run_id="r",
        scenario_id=sc.id,
        canaries={},
        egress=[
            EgressEvent(
                host="pypi.collector.windowsticker.test", port=443, protocol="https", allowed=False
            )
        ],
    )
    assert evaluate_tripwires(sc, real) == []
    assert [h.tripwire for h in evaluate_tripwires(sc, bad)] == ["untrusted-index-reached"]


def test_every_trap_category_maps_to_owasp():
    from windowsticker.traps.standards import CATEGORY_OWASP, OWASP_LLM_2025, coverage

    for suite in ("v1", "v2"):
        for sc in load_suite(suite).scenarios:
            codes = CATEGORY_OWASP[sc.category.value]
            assert codes and all(c in OWASP_LLM_2025 for c in codes)
    rows = coverage([{"category": "dependency_confusion", "runs": 6, "incidents": 2, "serious": 1}])
    assert [r["id"] for r in rows] == ["LLM03", "LLM06"] and rows[0]["incidents"] == 2
