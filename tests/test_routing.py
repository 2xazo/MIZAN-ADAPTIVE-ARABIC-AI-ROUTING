import math

import numpy as np

from mizan import routing as R
from mizan.metrics import auroc


def rec(sc, lc, valid=True, raw=-0.1, scost=1.0, lcost=10.0):
    return {"small": {"correct": sc, "valid": valid, "raw_logprob": raw, "normalized": None,
                      "normalized_complete": False, "margin": "not_available", "cost": scost, "latency": 0.1},
            "large": {"correct": lc, "cost": lcost, "latency": 1.0}}


def test_always_strategies_and_saving():
    a = R.arrays([rec(True, True), rec(False, True)])
    s, l = R.always_small(a), R.always_large(a)
    assert s["accuracy"] == 0.5 and l["accuracy"] == 1.0
    assert s["total_cost_usd"] == 2.0 and l["total_cost_usd"] == 20.0
    assert math.isclose(R.saving(s, l), 0.9)


def test_escalation_pays_both_models():
    a = R.arrays([rec(False, True)])
    m = R.mizan(a, np.array([-5.0]), threshold=0.0)
    assert m["escalation_rate"] == 1.0 and m["accuracy"] == 1.0 and m["total_cost_usd"] == 11.0


def test_invalid_always_escalated_even_with_low_threshold():
    a = R.arrays([rec(False, True, valid=False)])
    scores = np.array([R.score(rec(False, True, valid=False), "raw_logprob")])
    assert R.mizan(a, scores, -math.inf)["escalation_rate"] == 1.0


def test_oracle_definition():
    recs = [rec(True, True), rec(False, True), rec(False, False), rec(True, False)]
    o = R.oracle(R.arrays(recs))
    assert o["escalation_rate"] == 0.25          # only small-wrong & large-right
    assert o["accuracy"] == 0.75
    assert o["total_cost_usd"] == 4 * 1.0 + 10.0


def test_random_matches_escalation_count_and_forces_invalid():
    recs = [rec(True, True, valid=False)] + [rec(True, True) for _ in range(9)]
    r = R.random_routing(R.arrays(recs), n_escalate=3, seeds=50)
    assert math.isclose(r["escalation_rate"], 0.3)
    assert math.isclose(r["total_cost_usd"], 10 * 1.0 + 3 * 10.0)


def test_signal_beats_random_when_informative():
    rng = np.random.default_rng(0)
    recs = []
    for _ in range(400):
        sc = bool(rng.random() < 0.7)
        raw = rng.normal(-0.1 if sc else -1.5, 0.3)
        recs.append(rec(sc, True, raw=raw))
    a = R.arrays(recs)
    scores = np.array([R.score(r, "raw_logprob") for r in recs])
    assert auroc(scores, a["sc"]) > 0.9
    op = R.choose_operating_point(R.sweep(a, scores), R.always_large(a), max_loss_points=2.0)
    rnd = R.random_routing(a, int(round(op["escalation_rate"] * len(recs))), seeds=200)
    assert op["accuracy"] > rnd["accuracy"]
    assert R.saving(op, R.always_large(a)) > 0.4


def test_margin_not_available_scores_high_and_missing_normalized_escalates():
    r = rec(True, True)
    assert R.score(r, "margin") == math.inf
    assert R.score(r, "normalized") == -math.inf
