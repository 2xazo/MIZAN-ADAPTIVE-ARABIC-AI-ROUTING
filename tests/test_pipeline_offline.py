"""End-to-end offline: fake cached responses -> load_records -> analyze_pair. No network."""
import json
import random

from conftest import fake_response, tok
from mizan.analysis import analyze_pair
from mizan.client import cache_path
from mizan.runner import load_records

PRICES = {"models": {"small": {"input": 0.4, "output": 1.6}, "large": {"input": 2.0, "output": 8.0}}}
CRIT = {"min_small_accuracy": 0.5, "min_gap_points": 5, "min_auroc": 0.7, "max_loss_points": 2,
        "min_saving": 0.4, "borderline_auroc": [0.62, 0.75], "borderline_gap_points": [3, 5]}


def write(cache, model, item, content, entries):
    p = cache_path(cache, model, item["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"item_id": item["id"], "latency_s": 0.2,
                             "response": fake_response(content, entries)}), encoding="utf-8")


def test_offline_pipeline(tmp_path):
    rng = random.Random(0)
    items = []
    for i in range(200):
        it = {"id": f"q{i}", "level": f"L{i % 3}", "subject": "S", "country": "SA",
              "options": ["a", "b", "c", "d"], "answer": "A"}
        items.append(it)
        small_ok = rng.random() < 0.72
        p = rng.uniform(0.85, 0.99) if small_ok else rng.uniform(0.3, 0.6)
        letter = "A" if small_ok else "B"
        rest = (1 - p) / 3
        alts = {letter: p, **{l: rest for l in "ABCD" if l != letter}}
        write(tmp_path, "small", it, letter, [tok(letter, p, alts)])
        large_letter = "A" if rng.random() < 0.95 else "C"
        write(tmp_path, "large", it, large_letter, [tok(large_letter, 0.9)])
    # one malformed small output
    write(tmp_path, "small", items[0], "Answer: A", [tok("Answer", 0.5)])

    recs = load_records(items, "small", "large", PRICES, cache_dir=tmp_path)
    assert len(recs) == 200
    res = analyze_pair(recs, "small", "large", CRIT, seed=0, bootstrap_iters=100)
    assert res["invalid_small_outputs"] == 1
    assert res["decision"] == "GO", res["go_checks"]
    s = res["strategies"]
    assert s["mizan"]["accuracy"] > s["random"]["accuracy"]
    assert s["oracle"]["accuracy"] >= s["mizan"]["accuracy"]
    assert set(res["slices"]["level"]) == {"L0", "L1", "L2"}
    lo, hi = res["bootstrap_95ci"]["saving_vs_large"]
    assert lo <= s["mizan"]["saving_vs_large"] <= hi

    # Held-out mode: frozen threshold is reused, not re-tuned.
    held = analyze_pair(recs, "small", "large", CRIT, threshold=res["threshold"],
                        signal=res["selected_signal"])
    assert held["threshold"] == res["threshold"] and not held["threshold_tuned_on_these_records"]
