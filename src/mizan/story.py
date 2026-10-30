"""The story's numbers and copy, read from artifacts/heldout_results.json and never typed by hand.

`verify_approved_values` is the stop check: the app and the README refuse to build if a value in the
approved story differs from the results file.
"""
from __future__ import annotations

import json
import math

import numpy as np

from . import heldout as H
from .config import ARTIFACTS_DIR

RESULTS = ARTIFACTS_DIR / "heldout_results.json"
PER_ITEM = ARTIFACTS_DIR / "heldout_per_item.json"
EXAMPLES = ARTIFACTS_DIR / "demo_examples.json"

PROJECTION_TASKS = 1_000_000
FORBIDDEN = ("unseen", "works with any provider", "allam integration", "only where it adds value", "free verification", "beats random", "outperforms the mid-size model", "safe to trust", "model-agnostic", "statistically significant", "no extra model call")
SPLIT_SENTENCE = "The realized evaluation split was subject-by-level disjoint; the exact manifest was preserved, and the splitter was fixed with a regression test."
CORE_SENTENCE = "MIZAN lets an economical model answer first, and pays for the stronger model only when the answer itself shows doubt."
CORE_SENTENCE_TECHNICAL = "MIZAN lets an economical model answer first, and pays for the stronger model only when the answer itself shows doubt or fails output validation."
CONFIDENCE_CHECK = "The confidence check itself requires no additional model call."
ROUTING_LAYER = "provider-independent routing layer for models that expose token-level confidence"
HUMAIN_FIT = ("HUMAIN provides the Arabic model portfolio, sovereign infrastructure, and unified access layer. MIZAN adds the per-request decision: when is premium inference worth paying for?",
              "Adaptive reasoning optimizes how one model thinks. MIZAN optimizes which model should think in the first place.",
              "Today, MIZAN is validated on a publicly available reference pair. The next step is to evaluate the same confidence-aware routing through HUMAIN Node or HUMAIN IQ, subject to model access and confidence-signal availability.")
COST_BASIS = "Measured from recorded input/output tokens using the fixed prices documented in the repository."
SMALL, MID, LARGE = H.SMALL, H.MID, H.LARGE


def load_json(path=RESULTS) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def relative_error_reduction(res: dict) -> float:
    m = res["original"]["mechanism"]
    return (m["random_acceptance_risk"] - m["selective_risk"]) / m["random_acceptance_risk"]


def verify_approved_values(res: dict) -> None:
    """Raises if a displayed value differs from the values the coordinator approved."""
    o, s = res["original"], res["perturbation"]
    m = o["mechanism"]
    approved = [("saving vs Always gpt-4.1", o["mizan"]["saving_vs_top"] * 100, 66.45, 2),
                ("Mizan accuracy", o["mizan"]["accuracy"] * 100, 79.0, 1),
                ("Always gpt-4.1 accuracy", o["singles"][LARGE]["accuracy"] * 100, 82.6, 1),
                ("Mizan minus Always gpt-4o-mini", o["non_dominance"]["paired"][SMALL]["accuracy_diff"]["observed"] * 100, 5.4, 1),
                ("accepted-set error", m["selective_risk"] * 100, 15.82, 2),
                ("matched random acceptance error", m["random_acceptance_risk"] * 100, 26.40, 2),
                ("relative error reduction", relative_error_reduction(res) * 100, 40.08, 2),
                ("economical-model handling", m["coverage"] * 100, 74.6, 1),
                ("AUROC original", m["auroc"], 0.8214, 4),
                ("AUROC option-shuffle", s["mechanism"]["auroc"], 0.8248, 4),
                ("threshold", o["threshold"], 6.249999994711611, 15)]
    wrong = [f"{name}: results file {got!r}, approved {want!r}" for name, got, want, places in approved if round(got, places) != want]
    if wrong:
        raise ValueError("Approved story differs from artifacts/heldout_results.json: " + "; ".join(wrong))


def hero_copy(res: dict) -> dict:
    o = res["original"]
    return {"eyebrow": "Built for efficient Arabic AI at scale",
            "headline": "Does every Arabic task need the biggest model?",
            "subheadline": CORE_SENTENCE,
            "metric_value": f"{o['mizan']['saving_vs_top'] * 100:.0f}%",
            "metric_label": "LOWER MEASURED INFERENCE COST",
            "proofs": [f"{o['non_dominance']['paired'][SMALL]['accuracy_diff']['observed'] * 100:+.1f} accuracy points vs always using the economical model",
                       f"{relative_error_reduction(res) * 100:.0f}% fewer errors among accepted answers than matched random acceptance",
                       "Stable confidence after option-order shuffling"],
            "evaluation": f"Tested on {o['n']} held-out Arabic questions not used during development.",
            "tradeoff": f"MIZAN achieved {o['mizan']['accuracy'] * 100:.1f}% accuracy, compared with {o['singles'][LARGE]['accuracy'] * 100:.1f}% for always using {LARGE}."}


def impact_copy(res: dict) -> tuple[str, str]:
    cov = res["original"]["mechanism"]["coverage"]
    return (f"Projected at one million similar tasks: approximately {round(PROJECTION_TASKS * cov):,} handled without a high-capability model call.",
            f"Projected from the {cov * 100:.1f}% economical-model acceptance rate measured on held-out data.")


def directional_copy(res: dict) -> str:
    d = res["original"]["mizan_minus_random"]
    return f"{d['observed'] * 100:+.1f} pts [{d['ci95'][0] * 100:+.1f}, {d['ci95'][1] * 100:+.1f}]"


def chart_points(res: dict) -> list[dict]:
    o = res["original"]
    rows = [{"strategy": f"Always {m}", "accuracy": o["singles"][m]["accuracy"], "cost_usd": o["singles"][m]["total_cost_usd"]} for m in H.MODELS]
    rows.append({"strategy": "Matched Random", "accuracy": o["random"]["accuracy_mean"], "cost_usd": o["random"]["total_cost_usd_mean"]})
    rows.append({"strategy": "Mizan", "accuracy": o["mizan"]["accuracy"], "cost_usd": o["mizan"]["total_cost_usd"]})
    return rows


def robustness_rows(res: dict) -> list[dict]:
    o, s = res["original"], res["perturbation"]
    pick = [("Accuracy", lambda r: f"{r['mizan']['accuracy'] * 100:.1f}%"),
            ("AUROC", lambda r: f"{r['mechanism']['auroc']:.4f}"),
            ("Handled share", lambda r: f"{r['mechanism']['coverage'] * 100:.1f}%"),
            ("Saving", lambda r: f"{r['mizan']['saving_vs_top'] * 100:.2f}%")]
    return [{"metric": name, "original": fn(o), "shuffled": fn(s)} for name, fn in pick]


def replay_rows(per_item: dict, n: int | None = None) -> list[dict]:
    """Held-out items in run order with their recorded outcomes. All of them unless `n` is given."""
    orig, threshold = per_item["original"], per_item["threshold"]
    small, large = orig[SMALL], orig[LARGE]
    rows = []
    for k in range(len(per_item["ids"]) if n is None else n):
        margin = small["margin"][k]
        score = math.inf if margin == "inf" else (-math.inf if margin == "-inf" else margin)
        esc = (not small["valid"][k]) or score < threshold
        rows.append({"escalated": esc, "correct": large["correct"][k] if esc else small["correct"][k],
                     "cost_usd": small["cost_usd"][k] + (large["cost_usd"][k] if esc else 0.0), "always_large_cost_usd": large["cost_usd"][k]})
    return rows


def replay_totals(rows: list[dict]) -> dict:
    n = len(rows)
    esc = sum(r["escalated"] for r in rows)
    return {"processed": n, "handled": n - esc, "escalated": esc, "mizan_cost_usd": sum(r["cost_usd"] for r in rows),
            "always_large_cost_usd": sum(r["always_large_cost_usd"] for r in rows),
            "accuracy": sum(r["correct"] for r in rows) / n if n else 0.0}


def _run_arrays(run: dict) -> dict:
    out = {}
    for m in H.MODELS:
        d = run[m]
        score = np.array([math.inf if x == "inf" else (-math.inf if x == "-inf" else x) for x in d.get("margin", [0.0] * len(d["correct"]))], dtype=float)
        out[m] = {"correct": np.array(d["correct"], dtype=bool), "valid": np.array(d["valid"], dtype=bool),
                  "cost": np.array(d["cost_usd"], dtype=float), "score": score}
    return out


def _walk(path: str, got, want, diffs: list, counter: list) -> None:
    if isinstance(want, dict):
        for k in want:
            _walk(f"{path}.{k}", got.get(k) if isinstance(got, dict) else None, want[k], diffs, counter)
    elif isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            diffs.append((path, got, want))
            return
        for i, (a, b) in enumerate(zip(got, want)):
            _walk(f"{path}[{i}]", a, b, diffs, counter)
    else:
        counter.append(path)
        same = math.isclose(got, want, rel_tol=1e-9, abs_tol=1e-12) if isinstance(want, float) and isinstance(got, (int, float)) else got == want
        if not same:
            diffs.append((path, got, want))


def recompute_differences() -> tuple[list, int]:
    """Runs the evaluation's own analysis on the per-item table. Returns (differences, values checked)."""
    res, per = load_json(RESULTS), load_json(PER_ITEM)
    threshold = per["threshold"]
    orig, shuf = _run_arrays(per["original"]), _run_arrays(per["perturbation"])
    r0, r1 = H.analyze_run(orig, per["levels"], threshold), H.analyze_run(shuf, per["levels"], threshold)
    cmp_ = H.compare_runs(orig, shuf, r0, r1, threshold, np.array(per["position_dependent"], dtype=bool))
    recomputed = H.finite({"original": r0, "perturbation": r1, "comparison": cmp_})
    diffs, counter = [], []
    for part in ("original", "perturbation", "comparison"):
        _walk(part, recomputed[part], res[part], diffs, counter)
    return diffs, len(counter)
