"""Offline escalation-rate table for one pair, and the rule that picks the operating point.

Works on per-model arrays ({"correct", "valid", "cost", "score"}), so it is fully offline. Report
numbers are generated from the rows and are never typed by hand.
"""
from __future__ import annotations

import math

import numpy as np

from . import cascade as C

CURVE_GRID = tuple(i / 100 for i in range(0, 105, 5))  # declared before the table was computed
MAX_LOSS_POINTS = 4.0
EPS = 1e-9  # floating point only: 224/300 must count as equal to 236/300 - 0.04


def threshold_at(scores: np.ndarray, rate: float) -> float:
    """Numeric threshold for a target rate (score < threshold escalates). A target of 100% must
    also escalate the top score and `not_available` margins (+inf), so it is handled by `escalate`."""
    if rate >= 1.0:
        return math.inf
    return C.threshold_for_rate(scores, rate)


def escalate(valid: np.ndarray, scores: np.ndarray, threshold: float) -> np.ndarray:
    if threshold == math.inf:
        return np.ones(len(scores), dtype=bool)
    return (~valid) | (scores < threshold)


def always(model: dict) -> dict:
    return {"accuracy": float(model["correct"].mean()), "total_cost_usd": float(model["cost"].sum())}


def row(small: dict, large: dict, rate: float, baselines: dict[str, dict], seed: int,
        seeds: int = C.RANDOM_SEEDS) -> dict:
    threshold = threshold_at(small["score"], rate)
    esc = escalate(small["valid"], small["score"], threshold)
    correct = np.where(esc, large["correct"], small["correct"])
    cost = small["cost"] + np.where(esc, large["cost"], 0.0)
    n_esc = int(esc.sum())
    point = {"accuracy": float(correct.mean()), "total_cost_usd": float(cost.sum())}
    random_mean = C.random_chain([small, large], [n_esc], seeds=seeds, base_seed=seed)["accuracy"]["mean"]
    top = baselines[max(baselines, key=lambda k: baselines[k]["total_cost_usd"])]
    dominated = C.dominated_by(point, baselines)
    return {"target_rate": rate, "threshold": threshold, "escalated_items": n_esc, "achieved_rate": float(esc.mean()),
            **point, "saving_vs_top": 1.0 - point["total_cost_usd"] / top["total_cost_usd"],
            "accuracy_diff_vs_top": point["accuracy"] - top["accuracy"],
            "random_accuracy": random_mean, "mizan_minus_random": point["accuracy"] - random_mean,
            "accepted_accuracy": float(small["correct"][~esc].mean()) if (~esc).any() else None,
            "error_in_escalated": float((~small["correct"][esc]).mean()) if esc.any() else None,
            "dominated_by": dominated, "non_dominated": not dominated}


def table(small: dict, large: dict, baselines: dict[str, dict], seed: int, grid=CURVE_GRID,
          seeds: int = C.RANDOM_SEEDS) -> list[dict]:
    return [row(small, large, r, baselines, seed, seeds) for r in grid]


def choose_rule(rows: list[dict], top_accuracy: float, max_loss_points: float = MAX_LOSS_POINTS) -> dict | None:
    """The LOWEST target rate whose accuracy is >= Always-top minus the allowed loss. None = NO-GO."""
    floor = top_accuracy - max_loss_points / 100
    for r in sorted(rows, key=lambda x: x["target_rate"]):
        if r["accuracy"] >= floor - EPS:
            return r
    return None


# ---------------------------------------------------------------- report


def _thr(x: float) -> str:
    return "escalate all" if x == math.inf else "-inf" if x == -math.inf else f"{x:.4f}"


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


def report_md(rows: list[dict], chosen: dict | None, baselines: dict[str, dict], pair: str, signal: str,
              top_name: str, n: int, seeds: int) -> str:
    L = ["# MIZAN Dev 300 escalation table (exploratory)", "",
         f"Pair: `{pair}`. Signal: {signal}. Items: all {n} Dev. Random: {seeds} seeds, same number of escalated items. "
         "Held-out was not used. Dev 300 is exploratory; none of these numbers is a performance claim. "
         "The final hypothesis is formulated after Dev and before Held-out. Held-out is used once, as the only "
         "confirmation, and nothing changes after seeing it.", "",
         "| Always | Accuracy | Cost |", "|---|---|---|"]
    L += [f"| {k} | {_pct(v['accuracy'])} | ${v['total_cost_usd']:.5f} |" for k, v in baselines.items()]
    L += ["", "| Target | Threshold | Escalated | Achieved | Accuracy | Cost | Saving vs top | Acc diff vs top (pts) | "
          "Random mean | Mizan - Random (pts) | Accepted-set acc | Small error in escalated | Dominated by |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['target_rate'] * 100:.0f}% | {_thr(r['threshold'])} | {r['escalated_items']} | {_pct(r['achieved_rate'])} | "
                 f"{_pct(r['accuracy'])} | ${r['total_cost_usd']:.5f} | {_pct(r['saving_vs_top'])} | "
                 f"{r['accuracy_diff_vs_top'] * 100:+.2f} | {_pct(r['random_accuracy'])} | {r['mizan_minus_random'] * 100:+.2f} | "
                 f"{_pct(r['accepted_accuracy'])} | {_pct(r['error_in_escalated'])} | {', '.join(r['dominated_by']) or 'none'} |")
    L += ["", f"Top = Always {top_name}. Invalid small outputs count as errors and always escalate. "
          "Thresholds use `score < threshold`. Margins cluster near 0.25 steps with tiny floating-point noise, "
          "so that noise can split items of nearly equal margin at a threshold.", "",
          "Rule: the LOWEST escalation rate whose Dev 300 accuracy is >= Always top accuracy minus 4 percentage points.", ""]
    if chosen:
        L += [f"**Operating point: target {chosen['target_rate'] * 100:.0f}%, margin threshold {_thr(chosen['threshold'])}, "
              f"{chosen['escalated_items']} of {n} escalated, accuracy {_pct(chosen['accuracy'])}.**", ""]
    else:
        L += ["**NO-GO: no grid point satisfies the rule.**", ""]
    return "\n".join(L)
