"""Offline routing over an ordered chain of models (single, pair or three-step cascade).

Each model has one result per item, in the same item order:
    {"correct", "valid", "cost", "scores": {signal: float}, "confidence"}
A chain answers with the first model whose score reaches its threshold; the last model always
answers. Invalid output always escalates. Cost is the sum of every model actually called.
Nothing here calls an API, so changing a threshold never costs anything.
"""
from __future__ import annotations

import math
from itertools import product

import numpy as np

from .metrics import auroc

ESCALATION_GRID = tuple(i / 100 for i in range(0, 65, 5))  # fixed in advance; never expand
BOOTSTRAP_ITERS = 1000
RANDOM_SEEDS = 1000


def threshold_for_rate(scores: np.ndarray, rate: float) -> float:
    """Threshold that escalates about `rate` of `scores` (score < threshold escalates)."""
    s = np.sort(np.asarray(scores, dtype=float))
    k = int(round(rate * len(s)))
    if k <= 0 or len(s) == 0:
        return -math.inf
    return float(s[min(k, len(s) - 1)])


def simulate(models: list[dict], thresholds: list[float]) -> dict:
    """Route every item through the chain. `thresholds` has one value per non-final model."""
    n = len(models[0]["correct"])
    reached = np.ones(n, dtype=bool)
    correct = np.zeros(n, dtype=bool)
    cost = np.zeros(n)
    stops, escalations = [], []
    for i, m in enumerate(models):
        cost[reached] += m["cost"][reached]
        if i == len(models) - 1:
            esc = np.zeros(n, dtype=bool)
        else:
            esc = reached & ((~m["valid"]) | (m["score"] < thresholds[i]))
        stop = reached & ~esc
        correct[stop] = m["correct"][stop]
        stops.append(stop)
        escalations.append(esc)
        reached = esc
    return {"correct": correct, "cost": cost, "stops": stops, "escalations": escalations}


def summarize(sim: dict, names: list[str]) -> dict:
    n = len(sim["correct"])
    out = {"accuracy": float(sim["correct"].mean()), "total_cost_usd": float(sim["cost"].sum()),
           "mean_cost_usd": float(sim["cost"].mean()), "n": n,
           "stopped_at": {name: float(s.mean()) for name, s in zip(names, sim["stops"])},
           "achieved_escalation": []}
    reached = n
    for esc in sim["escalations"][:-1]:
        out["achieved_escalation"].append(float(esc.sum() / reached) if reached else 0.0)
        reached = int(esc.sum())
    return out


def grid_points(models: list[dict]) -> list[dict]:
    """All fixed grid points for a chain, with thresholds computed from these (tuning) items.
    The second-stage rate is conditional: it is a share of the items that reached stage 2."""
    if len(models) == 1:
        return [{"target": [], "thresholds": []}]
    points = []
    if len(models) == 2:
        for r in ESCALATION_GRID:
            points.append({"target": [r], "thresholds": [threshold_for_rate(models[0]["score"], r)]})
        return points
    for r1, r2 in product(ESCALATION_GRID, ESCALATION_GRID):
        t1 = threshold_for_rate(models[0]["score"], r1)
        first = simulate(models[:1] + [models[-1]], [t1])["escalations"][0]
        # With nothing reaching stage 2 on these items, fall back to the whole distribution.
        pool = models[1]["score"][first] if first.any() else models[1]["score"]
        points.append({"target": [r1, r2], "thresholds": [t1, threshold_for_rate(pool, r2)]})
    return points


def choose_point(models: list[dict], points: list[dict], objective: str, max_cost: float | None = None,
                 min_accuracy: float | None = None) -> dict | None:
    """primary: highest accuracy with cost <= max_cost. secondary: lowest cost with accuracy >= min_accuracy.
    Ties go to the lower cost, then to the fewest escalations (the grid's earliest point)."""
    best, best_key = None, None
    for p in points:
        sim = simulate(models, p["thresholds"])
        acc, cost = float(sim["correct"].mean()), float(sim["cost"].sum())
        if objective == "primary":
            if cost > max_cost + 1e-12:
                continue
            key = (-round(acc, 9), round(cost, 12))
        else:
            if acc < min_accuracy - 1e-9:
                continue
            key = (round(cost, 12), -round(acc, 9))
        if best_key is None or key < best_key:
            best, best_key = p, key
    return best


def signal_stats(correct: np.ndarray, valid: np.ndarray, scores: np.ndarray, confidence: np.ndarray) -> dict:
    """AUROC for the signal, and overconfidence: mean p(chosen answer) minus accuracy."""
    return {"auroc": auroc(scores, correct),
            "mean_confidence": float(confidence[valid].mean()) if valid.any() else None,
            "accuracy": float(correct.mean()),
            "overconfidence": float(confidence[valid].mean() - correct.mean()) if valid.any() else None}


def _interval(vals) -> dict:
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"mean": float(np.mean(vals)), "ci95": [float(lo), float(hi)]}


def _random_draw(models: list[dict], achieved_counts: list[int], rng) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """One random routing. Stage 2 is drawn only among items that reached it, so its conditional
    rate matches. Invalid outputs always escalate."""
    n = len(models[0]["correct"])
    reached = np.ones(n, dtype=bool)
    correct = np.zeros(n, dtype=bool)
    cost = np.zeros(n)
    counts = []
    for i, m in enumerate(models):
        cost[reached] += m["cost"][reached]
        esc = np.zeros(n, dtype=bool)
        if i < len(models) - 1:
            forced = np.flatnonzero(reached & ~m["valid"])
            free = np.flatnonzero(reached & m["valid"])
            esc[forced] = True
            k = max(0, min(len(free), achieved_counts[i] - len(forced)))
            if k:
                esc[rng.choice(free, size=k, replace=False)] = True
            counts.append(int(esc.sum()))
        stop = reached & ~esc
        correct[stop] = m["correct"][stop]
        reached = esc
    return correct, cost, counts


def random_chain(models: list[dict], achieved_counts: list[int], mizan_correct=None, seeds: int = RANDOM_SEEDS,
                 base_seed: int = 0) -> dict:
    """Random routing with the same escalation counts at each stage, over many seeds. With
    `mizan_correct`, also the paired difference: each iteration uses one random routing and one
    resample of items, applied to BOTH methods."""
    n = len(models[0]["correct"])
    accs, costs, realized, diffs = [], [], [], []
    for seed in range(seeds):
        rng = np.random.default_rng(base_seed + seed)
        correct, cost, counts = _random_draw(models, achieved_counts, rng)
        accs.append(float(correct.mean()))
        costs.append(float(cost.sum()))
        realized.append(counts)
        if mizan_correct is not None:
            idx = rng.integers(0, n, size=n)
            diffs.append(float(mizan_correct[idx].mean() - correct[idx].mean()))
    out = {"seeds": seeds, "accuracy": _interval(accs), "total_cost_usd": _interval(costs),
           "escalation_counts": [int(c) for c in realized[0]]}
    if mizan_correct is not None:
        d = _interval(diffs)
        out["paired_accuracy_diff"] = {"observed": float(mizan_correct.mean()) - out["accuracy"]["mean"],
                                       "boot_mean": d["mean"], "ci95": d["ci95"]}
    return out


def oracle_chain(models: list[dict]) -> dict:
    """Stop at the first model that answers correctly; if all are wrong, stay at the first model.
    Uses ground truth, so it is a theoretical upper bound, not a deployable router."""
    n = len(models[0]["correct"])
    correct = np.zeros(n, dtype=bool)
    cost = np.zeros(n)
    stopped = np.zeros((len(models), n), dtype=bool)
    for j in range(n):
        spent = 0.0
        for i, m in enumerate(models):
            spent += m["cost"][j]
            if m["correct"][j]:
                correct[j], cost[j] = True, spent
                stopped[i, j] = True
                break
        else:
            cost[j] = models[0]["cost"][j]
            stopped[0, j] = True
    return {"accuracy": float(correct.mean()), "total_cost_usd": float(cost.sum()),
            "stopped_at": [float(s.mean()) for s in stopped]}


def paired_bootstrap(correct_a, cost_a, correct_b, cost_b, iters: int = BOOTSTRAP_ITERS, seed: int = 0) -> dict:
    """A minus B. Both methods are resampled on the SAME items in each iteration."""
    ca, cb = np.asarray(correct_a, dtype=float), np.asarray(correct_b, dtype=float)
    pa, pb = np.asarray(cost_a, dtype=float), np.asarray(cost_b, dtype=float)
    n = len(ca)
    rng = np.random.default_rng(seed)
    d_acc, d_cost = np.empty(iters), np.empty(iters)
    for i in range(iters):
        idx = rng.integers(0, n, size=n)
        d_acc[i] = ca[idx].mean() - cb[idx].mean()
        d_cost[i] = pa[idx].sum() - pb[idx].sum()
    acc, cost = _interval(d_acc), _interval(d_cost)
    return {"iters": iters, "n": n,
            "accuracy_diff": {"observed": float(ca.mean() - cb.mean()), "boot_mean": acc["mean"], "ci95": acc["ci95"],
                              "ci_excludes_zero": bool(acc["ci95"][0] > 0 or acc["ci95"][1] < 0)},
            "cost_diff": {"observed": float(pa.sum() - pb.sum()), "boot_mean": cost["mean"], "ci95": cost["ci95"],
                          "ci_excludes_zero": bool(cost["ci95"][0] > 0 or cost["ci95"][1] < 0)}}


def dominated_by(design: dict, others: dict[str, dict], eps: float = 1e-12) -> list[str]:
    """Names of the others with accuracy >= and cost <= design, strictly better in at least one."""
    out = []
    for name, o in others.items():
        no_worse = o["accuracy"] >= design["accuracy"] - eps and o["total_cost_usd"] <= design["total_cost_usd"] + eps
        better = o["accuracy"] > design["accuracy"] + eps or o["total_cost_usd"] < design["total_cost_usd"] - eps
        if no_worse and better:
            out.append(name)
    return out


def pareto_frontier(designs: dict[str, dict]) -> list[str]:
    return [name for name, d in designs.items()
            if not dominated_by(d, {k: v for k, v in designs.items() if k != name})]
