"""Dev escalation table and the operating point rule on synthetic arrays. No network."""
import math

import numpy as np

from mizan import curve


def model(correct, score=None, cost=1.0, valid=None):
    n = len(correct)
    return {"correct": np.asarray(correct, dtype=bool), "cost": np.full(n, float(cost)),
            "valid": np.ones(n, dtype=bool) if valid is None else np.asarray(valid, dtype=bool),
            "score": np.arange(n, dtype=float) if score is None else np.asarray(score, dtype=float)}


def pair(n=20):
    # The small model is wrong on its 5 lowest scores; the large model is always right.
    return model(np.arange(n) >= 5, cost=1.0), model(np.ones(n), cost=10.0)


def rows(small, large, seeds=20):
    bases = {"s": curve.always(small), "m": {"accuracy": 0.8, "total_cost_usd": 40.0}, "t": curve.always(large)}
    return curve.table(small, large, bases, seed=0, seeds=seeds), bases


def test_grid_has_21_points_from_0_to_100():
    assert len(curve.CURVE_GRID) == 21 and curve.CURVE_GRID[0] == 0 and curve.CURVE_GRID[-1] == 1.0
    assert curve.CURVE_GRID[1] == 0.05


def test_zero_keeps_all_and_hundred_escalates_all_including_inf_scores():
    small, large = pair()
    small["score"][3] = math.inf
    t, _ = rows(small, large)
    assert t[0]["escalated_items"] == 0 and t[0]["accepted_accuracy"] == small["correct"].mean()
    assert t[0]["error_in_escalated"] is None
    last = t[-1]
    assert last["escalated_items"] == 20 and last["accepted_accuracy"] is None
    assert last["accuracy"] == 1.0 and last["total_cost_usd"] == 220.0  # the small call already happened


def test_row_metrics_on_a_known_point():
    small, large = pair()
    t, _ = rows(small, large)
    r = t[5]  # 25% = the 5 lowest scores, all wrong for the small model
    assert r["target_rate"] == 0.25 and r["escalated_items"] == 5
    assert r["accuracy"] == 1.0 and r["accepted_accuracy"] == 1.0 and r["error_in_escalated"] == 1.0
    assert r["total_cost_usd"] == 70.0
    assert math.isclose(r["saving_vs_top"], 1 - 70 / 200)
    assert r["accuracy_diff_vs_top"] == 0.0
    assert r["mizan_minus_random"] > 0
    assert r["accepted_accuracy"] is not None


def test_invalid_output_always_escalates_and_counts_as_error():
    small, large = pair()
    small["valid"][10] = False
    small["correct"][10] = False
    t, _ = rows(small, large)
    assert t[0]["escalated_items"] == 1 and t[0]["error_in_escalated"] == 1.0


def test_ties_are_reported_as_achieved_not_target():
    small, large = pair()
    small["score"] = np.array([1.0] * 10 + [2.0] * 10)
    t, _ = rows(small, large)
    by_target = {r["target_rate"]: r for r in t}
    assert by_target[0.25]["escalated_items"] == 0 and by_target[0.5]["escalated_items"] == 10


def test_dominance_against_baselines():
    small, large = pair()
    t, _ = rows(small, large)
    assert t[-1]["dominated_by"] == ["t"]  # same accuracy as the top model, higher cost
    assert t[5]["non_dominated"]


def test_rule_picks_lowest_rate_and_counts_exact_equality():
    r = [{"target_rate": 0.5, "accuracy": 0.9}, {"target_rate": 0.1, "accuracy": 0.5},
         {"target_rate": 0.3, "accuracy": 224 / 300}, {"target_rate": 0.4, "accuracy": 0.8}]
    assert curve.choose_rule(r, 236 / 300)["target_rate"] == 0.3


def test_rule_returns_none_when_nothing_qualifies():
    r = [{"target_rate": 0.0, "accuracy": 0.5}, {"target_rate": 1.0, "accuracy": 0.7}]
    assert curve.choose_rule(r, 0.8) is None


def test_threshold_is_never_inf_below_hundred_percent():
    small, _ = pair()
    assert curve.threshold_at(small["score"], 0.95) < math.inf
    assert curve.threshold_at(small["score"], 1.0) == math.inf
    assert curve.threshold_at(small["score"], 0.0) == -math.inf


def test_report_lists_every_grid_point_and_the_decision():
    small, large = pair()
    t, bases = rows(small, large)
    md = curve.report_md(t, t[5], bases, "s -> t", "margin", "t", 20, 20)
    assert md.count("%") and "exploratory" in md and "Operating point" in md
    assert all(f"| {r * 5}% |" in md for r in range(21))
    assert "NO-GO" in curve.report_md(t, None, bases, "s -> t", "margin", "t", 20, 20)
