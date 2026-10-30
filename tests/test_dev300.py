"""Dev 300 decision logic on synthetic per-model arrays. No network, no real data."""
import numpy as np

from mizan import dev300
from mizan.dev300 import CHEAP, MID, TOP, name_of


def fake_model(correct, score, cost):
    n = len(correct)
    score = np.asarray(score, dtype=float)
    return {"correct": np.asarray(correct, dtype=bool), "valid": np.ones(n, dtype=bool), "cost": np.full(n, float(cost)),
            "confidence": np.clip(score / 10, 0, 1), "normalized_complete": np.ones(n, dtype=bool),
            "margin_missing": np.zeros(n, dtype=bool),
            "scores": {"raw_logprob": score, "normalized": score, "margin": score}}


def data(seed=0, informative=True):
    rng = np.random.default_rng(seed)
    n = 300
    cheap = rng.random(n) < 0.70
    mid = cheap | (rng.random(n) < 0.35)
    top = mid | (rng.random(n) < 0.35)
    def scores(c):
        if informative:
            return np.where(c, rng.uniform(5, 10, n), rng.uniform(0, 6, n))
        return rng.uniform(0, 10, n)
    return {CHEAP: fake_model(cheap, scores(cheap), 0.15), MID: fake_model(mid, scores(mid), 0.40),
            TOP: fake_model(top, rng.uniform(0, 10, n), 2.0)}


def run(full):
    res = dev300.stamp(dev300.analyze_dev(full, [f"q{i}" for i in range(300)], seed=0))
    return res


def test_informative_routing_passes_and_report_has_all_sections():
    res = run(data())
    assert res["decision"] == "GO to held-out"
    assert res["designs"][res["chosen_design"]]["verdict"]["passes"]
    assert res["frozen"]["architecture"] == res["chosen_design"]
    assert len(res["designs"]) == 7
    md = dev300.report_md(res, 0.1, 8.0)
    for i in range(1, 16):
        assert f"## {i}. " in md
    assert "p95" not in md


def test_thresholds_come_from_first_100_only():
    full = data()
    a = run(full)
    changed = {m: {**v, "scores": {k: s.copy() for k, s in v["scores"].items()}} for m, v in full.items()}
    for s in changed[CHEAP]["scores"].values():
        s[100:] = 0.0  # only the confirmation scores change
    b = run(changed)
    for name in a["designs"]:
        pa, pb = a["designs"][name]["objectives"]["primary"], b["designs"][name]["objectives"]["primary"]
        assert pa.get("thresholds") == pb.get("thresholds") and pa.get("target_escalation") == pb.get("target_escalation")
    assert a["signals_chosen_on_first_100"] == b["signals_chosen_on_first_100"]


def test_all_dominated_is_no_go():
    # The mid model is right everywhere, so anything else is no better and costs the same or more;
    # the cheap model is wrong everywhere and any cheap-first route loses accuracy.
    n = 300
    rng = np.random.default_rng(1)
    full = {CHEAP: fake_model(np.zeros(n), rng.uniform(0, 10, n), 0.39),
            MID: fake_model(np.ones(n), rng.uniform(0, 10, n), 0.40),
            TOP: fake_model(np.ones(n), rng.uniform(0, 10, n), 2.0)}
    res = run(full)
    assert res["chosen_design"] is None and res["decision"] == "NO-GO" and res["frozen"] is None


def _ev(acc, cost, random_mean, escalated=10):
    return {"accuracy": acc, "total_cost_usd": cost, "escalated_items": [escalated],
            "random": {"accuracy": {"mean": random_mean}}}


SINGLES_200 = {CHEAP: {"accuracy": 0.70, "total_cost_usd": 1.0}, MID: {"accuracy": 0.78, "total_cost_usd": 3.0},
               TOP: {"accuracy": 0.80, "total_cost_usd": 15.0}}


def test_verdict_passes_only_when_it_beats_matched_random():
    chain = [CHEAP, TOP]
    assert dev300.verdict(chain, _ev(0.76, 2.0, 0.75), SINGLES_200, 3.0)["passes"]
    for random_mean in (0.76, 0.77):  # a tie is not a win
        v = dev300.verdict(chain, _ev(0.76, 2.0, random_mean), SINGLES_200, 3.0)
        assert not v["beats_random"] and not v["passes"] and not v["dominated_by"] and v["cost_within_limit"]


def test_verdict_other_binding_conditions_still_apply():
    chain = [CHEAP, TOP]
    assert dev300.verdict(chain, _ev(0.77, 4.0, 0.70), SINGLES_200, 3.0)["cost_within_limit"] is False
    assert dev300.verdict(chain, _ev(0.77, 3.5, 0.70), SINGLES_200, 3.5)["dominated_by"] == [MID]
    assert not dev300.verdict(chain, _ev(0.76, 2.0, 0.70, escalated=0), SINGLES_200, 3.0)["passes"]


def test_chosen_design_beats_random_mean():
    res = run(data())
    assert res["decision"] == "GO to held-out"
    ev = res["designs"][res["chosen_design"]]["objectives"]["primary"]["confirmation_200"]
    assert ev["random"]["accuracy"]["mean"] < ev["accuracy"]


def test_paired_random_difference_is_reported_with_ci():
    res = run(data())
    p = res["designs"][res["chosen_design"]]["objectives"]["primary"]["confirmation_200"]["random"]["paired_accuracy_diff"]
    assert p["ci95"][0] <= p["boot_mean"] <= p["ci95"][1]
    assert "Paired 95% CI" in dev300.report_md(res, 0.1, 8.0)


def test_zero_escalation_pair_does_not_pass_as_a_design():
    res = run(data())
    pair = res["designs"][name_of([MID, TOP])]
    # MID then TOP costs more than Always MID unless it never escalates.
    assert pair["verdict"]["degenerate_no_escalation"] and not pair["verdict"]["passes"]
