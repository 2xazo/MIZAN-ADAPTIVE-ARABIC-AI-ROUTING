"""Offline analysis of one (small, large) pair on stored records -> results dict + GO checks."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import routing as R
from .metrics import auroc, bootstrap_ci


def signal_report(records: list[dict], a: dict) -> dict:
    """AUROC of each signal for predicting 'small is correct', with coverage."""
    labels = a["sc"]
    out = {}
    for sig in R.SIGNALS:
        sc = np.array([R.score(r, sig) for r in records])
        valid = a["valid"]
        if sig == "normalized":
            cov = np.array([r["small"]["normalized_complete"] for r in records]) & valid
        elif sig == "margin":
            cov = np.array([r["small"]["margin"] != "not_available" for r in records]) & valid
        else:
            cov = valid
        out[sig] = {
            "auroc": auroc(sc, labels),
            "coverage_of_valid": float(cov.sum() / max(1, valid.sum())),
        }
    return out


def pick_signal(sig_rep: dict, min_cov_normalized: float = 0.95) -> str:
    """Highest AUROC on DEV. 'normalized' only eligible if the full distribution was visible
    for >= 95% of valid items (otherwise it is not a real distribution)."""
    eligible = {k: v for k, v in sig_rep.items() if v["auroc"] is not None
                and (k != "normalized" or v["coverage_of_valid"] >= min_cov_normalized)}
    if not eligible:
        return "raw_logprob"
    return max(eligible, key=lambda k: eligible[k]["auroc"])


def slices(records: list[dict], a: dict, scores: np.ndarray, thr: float, key: str) -> dict:
    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[r[key]].append(i)
    out = {}
    for g, idx in sorted(groups.items()):
        idx = np.array(idx)
        sub = {k: v[idx] for k, v in a.items()}
        m = R.mizan(sub, scores[idx], thr)
        L = R.always_large(sub)
        out[g] = {"n": int(len(idx)), "mizan_accuracy": m["accuracy"], "large_accuracy": L["accuracy"],
                  "small_accuracy": float(sub["sc"].mean()), "escalation_rate": m["escalation_rate"],
                  "saving": R.saving(m, L)}
    return out


def analyze_pair(records: list[dict], small: str, large: str, crit: dict,
                 threshold: float | None = None, signal: str | None = None,
                 bootstrap_iters: int = 0, seed: int = 0) -> dict:
    """If threshold/signal are None they are TUNED on these records (Dev). Pass the Dev-chosen
    values when evaluating Held-out so nothing is tuned on it."""
    a = R.arrays(records)
    tuned = threshold is None
    sig_rep = signal_report(records, a)
    signal = signal or pick_signal(sig_rep)
    scores = np.array([R.score(r, signal) for r in records])

    small_r, large_r, orc = R.always_small(a), R.always_large(a), R.oracle(a)
    points = R.sweep(a, scores)
    if tuned:
        op = R.choose_operating_point(points, large_r, crit["max_loss_points"])
        threshold = op["threshold"] if op else None
    miz = R.mizan(a, scores, threshold) if threshold is not None else None
    rnd = None
    if miz:
        n_esc = int(round(miz["escalation_rate"] * len(records)))
        rnd = R.random_routing(a, n_esc, seeds=1000, base_seed=seed)

    for p in [small_r, large_r, orc] + ([miz, rnd] if miz else []):
        p["saving_vs_large"] = R.saving(p, large_r)

    gap = (large_r["accuracy"] - small_r["accuracy"]) * 100
    sel_auroc = sig_rep[signal]["auroc"]
    checks = {
        "small_accuracy>=min": small_r["accuracy"] >= crit["min_small_accuracy"],
        "gap_points>=min": gap >= crit["min_gap_points"],
        "auroc>=min": sel_auroc is not None and sel_auroc >= crit["min_auroc"],
        "mizan_beats_random": bool(miz and rnd and miz["escalation_rate"] > 0
                                   and miz["accuracy"] > rnd["accuracy"] + 1e-9),
        "operating_point_loss<=max_and_saving>=min": bool(
            miz and (large_r["accuracy"] - miz["accuracy"]) * 100 <= crit["max_loss_points"] + 1e-9
            and miz["saving_vs_large"] >= crit["min_saving"]),
    }
    lo_a, hi_a = crit["borderline_auroc"]
    lo_g, hi_g = crit["borderline_gap_points"]
    borderline = bool((sel_auroc is not None and lo_a <= sel_auroc <= hi_a) or lo_g <= gap <= hi_g)
    if all(checks.values()):
        decision = "GO"
    elif borderline:
        decision = "BORDERLINE: raise Dev to 300 before NO-GO"
    else:
        decision = "NO-GO"

    res = {
        "pair": {"small": small, "large": large},
        "n": len(records),
        "invalid_small_outputs": int((~a["valid"]).sum()),
        "signals": sig_rep,
        "selected_signal": signal,
        "threshold": threshold,
        "threshold_tuned_on_these_records": tuned,
        "strategies": {"always_small": small_r, "always_large": large_r, "random": rnd,
                       "mizan": miz, "oracle": orc},
        "gap_points": gap,
        "curve": [{"threshold": p["threshold"], "accuracy": p["accuracy"],
                   "saving_vs_large": R.saving(p, large_r), "escalation_rate": p["escalation_rate"]}
                  for p in points],
        "slices": {"level": slices(records, a, scores, threshold, "level") if miz else {},
                   "country": slices(records, a, scores, threshold, "country") if miz else {}},
        "go_checks": checks,
        "decision": decision,
        "tokens": {
            "small_input": int(sum(r["small"]["input_tokens"] for r in records)),
            "small_output": int(sum(r["small"]["output_tokens"] for r in records)),
            "large_input": int(sum(r["large"]["input_tokens"] for r in records)),
            "large_output": int(sum(r["large"]["output_tokens"] for r in records)),
        },
    }

    if bootstrap_iters and miz:
        n = len(records)
        esc = (~a["valid"]) | (scores < threshold)

        def sub_acc(idx, which):
            c = np.where(esc[idx], a["lc"][idx], a["sc"][idx]) if which == "mizan" else a["lc"][idx]
            return float(c.mean())

        def sub_saving(idx):
            mc = (a["scost"][idx] + np.where(esc[idx], a["lcost"][idx], 0)).sum()
            return float(1 - mc / a["lcost"][idx].sum())

        res["bootstrap_95ci"] = {
            "mizan_accuracy": bootstrap_ci(n, lambda i: sub_acc(i, "mizan"), bootstrap_iters, seed),
            "large_accuracy": bootstrap_ci(n, lambda i: sub_acc(i, "large"), bootstrap_iters, seed),
            "saving_vs_large": bootstrap_ci(n, sub_saving, bootstrap_iters, seed),
        }
    return res
