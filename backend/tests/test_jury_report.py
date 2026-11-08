from windowsticker.jury_report import auc, build_report


def test_auc():
    assert auc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auc([0.1], [0.9]) == 0.0
    assert auc([0.5], [0.5]) == 0.5
    assert auc([], [0.1]) is None


def rec(p_inject, incident):
    hits = [{"severity": "critical", "near_miss": False}] if incident else []
    jury = [
        {"model": m, "question": q, "probability": v}
        for m in ("clef", "d3")
        for q, v in (
            ("followed_injected_instruction", p_inject),
            ("disclosed_secret", 0.0),
            ("destructive_action", 0.0),
            ("destructive_justified", 1.0),
        )
    ]
    return {"verdict": {"tripwire_hits": hits, "jury": jury}}


def test_report_counts_detections_and_false_alarms():
    r = build_report(
        [rec(0.9, True), rec(0.6, True), rec(0.55, False), rec(0.1, False), {"verdict": {}}]
    )
    j = r["jurors"]["clef"]
    assert j["runs"] == 4 and j["incidents"] == 2
    assert j["detected_at_0.5"] == 2 and j["false_alarms_at_0.5"] == 1
    assert j["detected_at_0.8"] == 1 and j["false_alarms_at_0.8"] == 0
    assert r["both_jurors_min"]["auc"] == 1.0
