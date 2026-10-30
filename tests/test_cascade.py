"""Cascade analysis: routing, thresholds, conditional random, oracle, paired bootstrap, dominance."""
import math

import numpy as np

from mizan import cascade as C


def model(correct, score=None, cost=1.0, valid=None):
    correct = np.array(correct, dtype=bool)
    n = len(correct)
    return {"correct": correct, "valid": np.ones(n, dtype=bool) if valid is None else np.array(valid, dtype=bool),
            "cost": np.full(n, float(cost)), "score": np.arange(n, dtype=float) if score is None else np.array(score, dtype=float)}


def test_threshold_for_rate_hits_target_and_zero_escalates_nothing():
    s = np.arange(100, dtype=float)
    assert C.threshold_for_rate(s, 0.0) == -math.inf
    for r in (0.05, 0.25, 0.6):
        assert (s < C.threshold_for_rate(s, r)).mean() == r


def test_grid_is_fixed_size():
    assert len(C.ESCALATION_GRID) == 13 and C.ESCALATION_GRID[-1] == 0.6
    a, b, c = model([1] * 20), model([1] * 20), model([1] * 20)
    assert len(C.grid_points([a, c])) == 13
    assert len(C.grid_points([a, b, c])) == 169


def test_chain_pays_every_model_called_and_stops_correctly():
    a = model([1, 0, 0], score=[9, 1, 1], cost=1)
    b = model([0, 1, 0], score=[9, 9, 1], cost=10)
    c = model([0, 0, 1], score=[9, 9, 9], cost=100)
    sim = C.simulate([a, b, c], [5, 5])
    assert sim["correct"].tolist() == [True, True, True]
    assert sim["cost"].tolist() == [1, 11, 111]
    assert [s.tolist() for s in sim["stops"]] == [[True, False, False], [False, True, False], [False, False, True]]


def test_invalid_output_escalates_even_at_zero_rate():
    a = model([0, 1], score=[9, 9], valid=[False, True])
    b = model([1, 1], cost=5)
    sim = C.simulate([a, b], [-math.inf])
    assert sim["escalations"][0].tolist() == [True, False]
    assert sim["correct"].tolist() == [True, True]


def test_achieved_second_stage_rate_is_conditional():
    a = model([1] * 10, score=list(range(10)))
    b = model([1] * 10, score=list(range(10)))
    c = model([1] * 10)
    s = C.summarize(C.simulate([a, b, c], [4, 2]), ["a", "b", "c"])
    assert s["achieved_escalation"] == [0.4, 0.5]  # 4 of 10, then 2 of the 4 that reached stage 2
    assert s["stopped_at"] == {"a": 0.6, "b": 0.2, "c": 0.2}


def test_conditional_random_matches_counts_and_only_draws_from_reached():
    n = 50
    a, b, c = model([1] * n, cost=1), model([1] * n, cost=10), model([1] * n, cost=100)
    r = C.random_chain([a, b, c], [20, 5], seeds=50)
    assert r["escalation_counts"] == [20, 5]
    # Fixed counts mean a fixed cost: 50*1 + 20*10 + 5*100.
    assert r["total_cost_usd"]["mean"] == 750 and r["total_cost_usd"]["ci95"] == [750, 750]


def test_paired_random_difference_is_zero_when_every_route_is_right():
    n = 40
    a, b = model([1] * n), model([1] * n, cost=5)
    r = C.random_chain([a, b], [10], mizan_correct=np.ones(n, dtype=bool), seeds=50)
    assert r["paired_accuracy_diff"]["observed"] == 0 and r["paired_accuracy_diff"]["ci95"] == [0, 0]


def test_random_stage2_invalid_counts_toward_the_match():
    n = 20
    a = model([1] * n, cost=1)
    b = model([1] * n, cost=10, valid=[False] * 3 + [True] * (n - 3))
    c = model([1] * n, cost=100)
    r = C.random_chain([a, b, c], [n, 5], seeds=20)  # everything reaches stage 2
    assert r["escalation_counts"] == [n, 5]


def test_cascade_oracle_stops_at_first_correct_and_stays_first_if_all_wrong():
    a = model([1, 0, 0, 0], cost=1)
    b = model([0, 1, 0, 0], cost=10)
    c = model([0, 0, 1, 0], cost=100)
    o = C.oracle_chain([a, b, c])
    assert o["accuracy"] == 0.75
    assert o["total_cost_usd"] == 1 + 11 + 111 + 1
    assert o["stopped_at"] == [0.5, 0.25, 0.25]


def test_paired_bootstrap_identical_methods_give_zero():
    x = np.array([1, 0, 1, 1, 0] * 10, dtype=bool)
    r = C.paired_bootstrap(x, np.ones(50), x, np.ones(50), iters=200)
    assert r["accuracy_diff"]["ci95"] == [0, 0] and not r["accuracy_diff"]["ci_excludes_zero"]
    assert r["cost_diff"]["ci95"] == [0, 0]


def test_paired_bootstrap_detects_real_difference_and_uses_same_items():
    good = np.ones(100, dtype=bool)
    bad = np.array([True, False] * 50)
    r = C.paired_bootstrap(good, np.full(100, 2.0), bad, np.ones(100), iters=300)
    assert r["accuracy_diff"]["observed"] == 0.5 and r["accuracy_diff"]["ci_excludes_zero"]
    # Costs are constant per item, so with paired resampling the difference never varies.
    assert r["cost_diff"]["ci95"] == [100, 100]


def test_dominance_requires_no_worse_on_both_and_strictly_better_on_one():
    d = {"accuracy": 0.78, "total_cost_usd": 0.012}
    assert C.dominated_by(d, {"m": {"accuracy": 0.79, "total_cost_usd": 0.007}}) == ["m"]
    assert C.dominated_by(d, {"m": {"accuracy": 0.78, "total_cost_usd": 0.007}}) == ["m"]
    assert C.dominated_by(d, {"m": {"accuracy": 0.79, "total_cost_usd": 0.012}}) == ["m"]
    assert C.dominated_by(d, {"m": {"accuracy": 0.78, "total_cost_usd": 0.012}}) == []  # identical
    assert C.dominated_by(d, {"m": {"accuracy": 0.90, "total_cost_usd": 0.020}}) == []  # trade-off


def test_pareto_frontier_keeps_only_non_dominated():
    designs = {"cheap": {"accuracy": 0.7, "total_cost_usd": 1}, "mid": {"accuracy": 0.8, "total_cost_usd": 2},
               "bad": {"accuracy": 0.75, "total_cost_usd": 3}, "top": {"accuracy": 0.9, "total_cost_usd": 5}}
    assert C.pareto_frontier(designs) == ["cheap", "mid", "top"]


def test_choose_point_primary_respects_cost_and_prefers_cheaper_on_tie():
    a = model([1, 0, 0, 0], score=[4, 1, 2, 3], cost=1)
    b = model([1, 1, 0, 0], cost=10)
    pts = [{"target": [0.0], "thresholds": [-math.inf]}, {"target": [0.25], "thresholds": [2.0]},
           {"target": [0.5], "thresholds": [3.0]}]
    assert C.choose_point([a, b], pts, "primary", max_cost=15)["target"] == [0.25]
    assert C.choose_point([a, b], pts, "primary", max_cost=5)["target"] == [0.0]


def test_choose_point_secondary_is_cheapest_meeting_accuracy():
    a = model([1, 0, 0, 0], score=[4, 1, 2, 3], cost=1)
    b = model([1, 1, 0, 0], cost=10)
    pts = [{"target": [0.0], "thresholds": [-math.inf]}, {"target": [0.25], "thresholds": [2.0]},
           {"target": [0.5], "thresholds": [3.0]}]
    assert C.choose_point([a, b], pts, "secondary", min_accuracy=0.5)["target"] == [0.25]
    assert C.choose_point([a, b], pts, "secondary", min_accuracy=0.9) is None
