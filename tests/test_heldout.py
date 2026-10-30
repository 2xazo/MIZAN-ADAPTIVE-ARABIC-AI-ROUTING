"""Offline tests for the held-out analysis, on synthetic arrays only. Held-out is never read."""
import json
import math

import numpy as np

from mizan import heldout as H


def model(correct, valid=None, cost=0.001, score=None):
    correct = np.array(correct, dtype=bool)
    n = len(correct)
    return {"correct": correct, "valid": np.ones(n, dtype=bool) if valid is None else np.array(valid, dtype=bool),
            "cost": np.full(n, cost), "score": np.zeros(n) if score is None else np.array(score, dtype=float)}


def fixture(n=200):
    # The small model is wrong exactly where its margin is low, and the large model is right there.
    low = np.arange(n) < n // 4
    return {H.SMALL: model(~low, cost=0.0001, score=np.where(low, 1.0, 9.0)),
            H.MID: model(np.arange(n) % 10 != 0, cost=0.0003), H.LARGE: model(np.arange(n) % 20 != 0, cost=0.002)}


def test_classify_primary():
    assert H.classify_primary(0.03, [0.01, 0.05]) == H.STRONG
    assert H.classify_primary(0.03, [-0.01, 0.05]) == H.TREND
    assert H.classify_primary(0.0, [-0.01, 0.01]) == H.FAILURE
    assert H.classify_primary(-0.01, [-0.03, 0.01]) == H.FAILURE


def test_same_sign_zero_only_matches_zero():
    assert H.same_sign(0.02, 0.01)
    assert not H.same_sign(0.02, -0.01)
    assert not H.same_sign(0.02, 0.0)
    assert H.same_sign(0.0, 0.0)


def test_decide_mapping():
    assert H.decide(H.STRONG, False, True)[0] == H.GO
    assert H.decide(H.STRONG, True, True)[0] == H.CONDITIONAL
    assert H.decide(H.STRONG, False, False)[0] == H.CONDITIONAL
    assert H.decide(H.TREND, False, True)[0] == H.CONDITIONAL
    assert H.decide(H.TREND, True, True)[0] == H.NO_GO
    assert H.decide(H.TREND, False, False)[0] == H.NO_GO
    assert H.decide(H.FAILURE, False, True)[0] == H.NO_GO


def test_threshold_is_strict_and_routes_to_large():
    f = fixture()
    r = H.analyze_run(f, ["a"] * 200, threshold=1.0)  # score == threshold does not escalate
    assert r["mizan"]["escalated_items"] == 0
    r = H.analyze_run(f, ["a"] * 200, threshold=5.0)
    assert r["mizan"]["escalated_items"] == 50
    assert r["mizan"]["accuracy"] == float(np.where(np.arange(200) < 50, f[H.LARGE]["correct"], f[H.SMALL]["correct"]).mean())
    assert math.isclose(r["mizan"]["total_cost_usd"], 200 * 0.0001 + 50 * 0.002)
    assert r["mechanism"]["coverage"] == 0.75
    assert r["mechanism"]["selective_risk"] == 0.0
    assert r["mechanism"]["small_error_in_escalated"] == 1.0
    assert r["primary"] == H.STRONG


def test_invalid_always_escalates_and_inf_never_does():
    f = fixture(8)
    f[H.SMALL] = model([0, 1, 1, 1, 1, 1, 1, 1], valid=[0, 1, 1, 1, 1, 1, 1, 1], cost=0.0001,
                       score=[-math.inf, math.inf, 9, 9, 9, 9, 9, 9])
    r = H.analyze_run(f, ["a"] * 8, threshold=5.0)
    assert r["mizan"]["escalated_items"] == 1
    assert r["mizan"]["invalid_outputs"] == 1
    assert r["mizan"]["not_available_margins"] == 1


def test_random_matches_achieved_count():
    r = H.analyze_run(fixture(), ["a"] * 200, threshold=5.0)
    assert r["random"]["escalation_counts"] == [50]
    assert r["random"]["seeds"] == 1000


def test_compare_runs_paired_and_claims():
    f, g = fixture(), fixture()
    g[H.SMALL]["score"] = np.where(np.arange(200) < 60, 1.0, 9.0)  # 10 items newly escalated
    r0, r1 = H.analyze_run(f, ["a"] * 200, 5.0), H.analyze_run(g, ["a"] * 200, 5.0)
    c = H.compare_runs(f, g, r0, r1, 5.0, np.zeros(200, dtype=bool))
    assert c["routing_decisions_changed"] == 10
    assert c["stayed_to_escalated"] == 10
    assert c["escalated_to_stayed"] == 0
    assert c["score_change"]["both_finite"] == 200
    assert c["claims"]["same_sign"]


def test_auroc_drop_over_limit_fails_claim():
    f, g = fixture(), fixture()
    g[H.SMALL]["score"] = np.zeros(200)
    r0, r1 = H.analyze_run(f, ["a"] * 200, 5.0), H.analyze_run(g, ["a"] * 200, 5.0)
    c = H.compare_runs(f, g, r0, r1, 5.0, np.zeros(200, dtype=bool))
    assert not c["claims"]["auroc_within_005"]
    assert not c["claims"]["both_hold"]


def test_finite_makes_strict_json():
    assert json.loads(json.dumps(H.finite({"a": math.inf, "b": [-math.inf, 1.0]}), allow_nan=False)) == {"a": "inf", "b": ["-inf", 1.0]}
