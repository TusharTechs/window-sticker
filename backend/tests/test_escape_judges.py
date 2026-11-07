"""The escape-matrix judges decide contained/escaped from evidence; test them on real outputs."""

from windowsticker.escape.matrix import PAYLOADS
from windowsticker.sandbox.base import ExecResult

J = {p.id: p.judge for p in PAYLOADS}
HOST = {
    "kernel": "6.8.0-147-generic",
    "secret_values": ["sk-real-1", "tok-real-2"],
    "before": {},
    "after": {},
}


def r(stdout="", stderr="", code=0):
    return ExecResult(code, stdout, stderr, 0.1)


def test_metadata_denied_vs_leaked():
    assert J["metadata-direct"](r('{"code":"network_policy_denied"}'), [], HOST).contained
    assert not J["metadata-direct"](r('{"instanceid":"abc","hostname":"x"}'), [], HOST).contained


def test_udp_dns_nxdomain_is_contained_but_real_answers_are_not():
    assert J["direct-udp-dns"](r("rcode 3 answers 0"), [], HOST).contained
    assert not J["direct-udp-dns"](r("rcode 0 answers 2"), [], HOST).contained


def test_raw_http_only_runtime_denials_count_as_contained():
    denied = "10.0.0.1 b'HTTP/1.1 403 Forbidden ... network_policy_denied'\n1.1.1.1 ConnectionRefusedError"
    assert J["private-network"](r(denied), [], HOST).contained
    assert not J["private-network"](r("1.1.1.1 b'HTTP/1.1 301 Moved'"), [], HOST).contained


def test_env_judges_values_not_names():
    assert J["env-secrets"](
        r("GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305\nPATH=/bin"), [], HOST
    ).contained
    assert not J["env-secrets"](r("X=sk-real-1"), [], HOST).contained
    assert not J["env-secrets"](
        r("PATH=/bin"), [], {**HOST, "secret_values": []}
    ).contained  # inconclusive


def test_kernel_and_kvm():
    assert J["separate-kernel"](r("6.12.113\n"), [], HOST).contained
    assert not J["separate-kernel"](r("6.8.0-147-generic\n"), [], HOST).contained
    assert J["kvm-device"](r("NO-KVM"), [], HOST).contained


def test_warden_refusal_is_contained():
    ev = [
        {"allowed": False, "protocol": "https", "host": "collector.windowsticker.test", "port": 443}
    ]
    assert J["https-exfil"](r("000"), ev, HOST).contained
    assert not J["https-exfil"](r("200 ESCAPED-HTTP"), [], HOST).contained


def test_resource_judge_requires_host_headroom():
    ok = {
        **HOST,
        "before": {"mem_free_mib": 6000, "disk_free_gib": 90},
        "after": {"mem_free_mib": 5800, "disk_free_gib": 90},
    }
    bad = {**ok, "after": {"mem_free_mib": 100, "disk_free_gib": 90}}
    assert J["memory-bomb"](r(), [], ok).contained
    assert not J["memory-bomb"](r(), [], bad).contained


def test_published_matrix_is_all_contained():
    import json
    from pathlib import Path

    data = json.loads(
        (Path(__file__).parents[1] / "windowsticker" / "escape_matrix.json").read_text()
    )
    assert data["total"] == len(PAYLOADS) == 17
    assert data["contained"] == data["total"]
    # No secret value is ever written out: check against every value in the local .env, if any.
    env = Path(__file__).parents[2] / ".env"
    blob = json.dumps(data)
    if env.exists():
        for line in env.read_text().splitlines():
            _, _, value = line.partition("=")
            if len(value) >= 16:
                assert value not in blob
