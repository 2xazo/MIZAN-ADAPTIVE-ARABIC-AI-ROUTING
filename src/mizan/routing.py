"""Routing strategies, all computed OFFLINE from stored per-item results.

Each record: {"id", "level", "subject", "small": {...}, "large": {...}} where each side has
`correct` (bool), `cost` (USD), `latency` (s); small additionally has `valid` and signals.

Escalated cost = small cost + large cost (the small call already happened).
"""
from __future__ import annotations

import math

import numpy as np

SIGNALS = ("raw_logprob", "normalized", "margin")


def score(rec: dict, signal: str) -> float:
    """Higher = more confident. Invalid outputs get -inf (always escalated)."""
    s = rec["small"]
    if not s["valid"]:
        return -math.inf
    v = s.get(signal)
    if signal == "margin" and v == "not_available":
        # No valid competitor in top_logprobs: competitor mass is below the k-th token,
        # i.e. the model is at least as sure as any measurable margin. Documented choice.
        return math.inf
    if v is None:
        return -math.inf  # signal unavailable for this item -> conservative: escalate
    return float(v)


def _summ(correct: np.ndarray, cost: np.ndarray, latency: np.ndarray, escalated: np.ndarray) -> dict:
    return {
        "accuracy": float(correct.mean()),
        "total_cost_usd": float(cost.sum()),
        "mean_cost_usd": float(cost.mean()),
        "latency_p50_s": float(np.percentile(latency, 50)),
        "latency_p95_s": float(np.percentile(latency, 95)),
        "escalation_rate": float(escalated.mean()),
        "n": int(len(correct)),
    }


def arrays(records: list[dict]) -> dict:
    g = lambda side, k: np.array([r[side][k] for r in records], dtype=float)
    return {
        "sc": g("small", "correct").astype(bool), "lc": g("large", "correct").astype(bool),
        "scost": g("small", "cost"), "lcost": g("large", "cost"),
        "slat": g("small", "latency"), "llat": g("large", "latency"),
        "valid": np.array([r["small"]["valid"] for r in records], dtype=bool),
    }


def route(a: dict, escalate: np.ndarray) -> dict:
    correct = np.where(escalate, a["lc"], a["sc"])
    cost = a["scost"] + np.where(escalate, a["lcost"], 0.0)
    lat = a["slat"] + np.where(escalate, a["llat"], 0.0)
    return _summ(correct, cost, lat, escalate)


def always_small(a: dict) -> dict:
    return route(a, np.zeros_like(a["sc"]))


def always_large(a: dict) -> dict:
    return _summ(a["lc"], a["lcost"], a["llat"], np.ones_like(a["lc"]))


def mizan(a: dict, scores: np.ndarray, threshold: float) -> dict:
    esc = (~a["valid"]) | (scores < threshold)
    out = route(a, esc)
    out["threshold"] = float(threshold)
    return out


def oracle(a: dict) -> dict:
    """Escalate only when small is wrong AND large is right (uses ground truth: upper bound)."""
    return route(a, (~a["sc"]) & a["lc"])


def random_routing(a: dict, n_escalate: int, seeds: int = 1000, base_seed: int = 0) -> dict:
    """Same number of escalations as Mizan. Invalid outputs are always escalated (as in Mizan);
    the remaining escalations are drawn at random. Isolates the value of the confidence signal."""
    n = len(a["sc"])
    forced = np.flatnonzero(~a["valid"])
    free = np.flatnonzero(a["valid"])
    k = max(0, min(len(free), n_escalate - len(forced)))
    accs, costs = [], []
    for s in range(seeds):
        rng = np.random.default_rng(base_seed + s)
        esc = np.zeros(n, dtype=bool)
        esc[forced] = True
        if k:
            esc[rng.choice(free, size=k, replace=False)] = True
        r = route(a, esc)
        accs.append(r["accuracy"])
        costs.append(r["total_cost_usd"])
    out = route(a, esc)  # latency/rate from last draw (identical rate for all draws)
    out.update(accuracy=float(np.mean(accs)), accuracy_std=float(np.std(accs)),
               total_cost_usd=float(np.mean(costs)), mean_cost_usd=float(np.mean(costs)) / n,
               seeds=seeds)
    return out


def sweep(a: dict, scores: np.ndarray) -> list[dict]:
    """Every distinct operating point (escalate everything below each threshold)."""
    finite = np.unique(scores[np.isfinite(scores)])
    thresholds = [-math.inf] + list(finite) + [math.inf]
    return [mizan(a, scores, t) for t in thresholds]


def choose_operating_point(points: list[dict], large: dict, max_loss_points: float) -> dict | None:
    """Max saving subject to accuracy loss vs Always-Large <= max_loss_points (chosen on DEV)."""
    ok = [p for p in points
          if (large["accuracy"] - p["accuracy"]) * 100 <= max_loss_points + 1e-9]
    if not ok:
        return None
    return min(ok, key=lambda p: (p["total_cost_usd"], -p["accuracy"]))


def saving(p: dict, large: dict) -> float:
    return 1.0 - p["total_cost_usd"] / large["total_cost_usd"] if large["total_cost_usd"] else 0.0
