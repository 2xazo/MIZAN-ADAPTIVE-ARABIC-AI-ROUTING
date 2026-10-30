"""Offline held-out analysis: preregistration sections 8 to 11, at the frozen point only.

Works on per-model arrays, so it is fully offline. Nothing here picks or changes a threshold, and
the decision mapping is fixed in code before any held-out call. Report numbers are generated from
the results dict and are never typed by hand.
"""
from __future__ import annotations

import math

import numpy as np

from . import cascade as C
from .metrics import auroc, bootstrap_ci

SMALL, MID, LARGE = "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"
MODELS = (SMALL, MID, LARGE)
SEED = 42
ITERS = 1000
MIZAN = f"Mizan {SMALL} -> {LARGE}"
AUROC_MAX_DROP = 0.05
ZERO_EPS = 1e-9  # floating point only, for the sign of Mizan minus Random
SMALL_SLICE = 30

STRONG, TREND, FAILURE = "Strong success", "Inconclusive trend", "Failure"
GO, CONDITIONAL, NO_GO = ("GO for building the UI, presentation and video.", "Conditional GO with limited claims.",
                          "NO-GO")


def classify_primary(diff: float, ci95: list[float]) -> str:
    """Section 9. A positive difference whose CI includes zero is not a success."""
    if diff <= ZERO_EPS:
        return FAILURE
    return STRONG if ci95[0] > 0 else TREND


def sign(x: float) -> int:
    return 0 if abs(x) <= ZERO_EPS else (1 if x > 0 else -1)


def same_sign(a: float, b: float) -> bool:
    """Section 11. A zero on either side counts as the same sign only if both are zero."""
    return sign(a) == sign(b)


def decide(primary: str, dominated: bool, robust: bool) -> tuple[str, str]:
    """Fixed before held-out. Failure stops the work (section 10). Strong success with non-dominance
    and both robustness claims is a GO. An inconclusive trend with another failed check is a NO-GO.
    Anything else allows only limited claims."""
    if primary == FAILURE:
        return NO_GO, "The primary claim failed: Mizan does not beat matched Random."
    if primary == TREND and (dominated or not robust):
        return NO_GO, "The primary claim is only an inconclusive trend, and non-dominance or robustness also failed."
    if primary == STRONG and not dominated and robust:
        return GO, "Strong primary success, not dominated by a single model, and both robustness claims hold."
    reasons = []
    if primary == TREND:
        reasons.append("the gain over matched Random is an inconclusive trend, not a success")
    if dominated:
        reasons.append("a single model dominates the operating point")
    if not robust:
        reasons.append("a registered robustness claim failed")
    return CONDITIONAL, "; ".join(reasons).capitalize() + "."


def _acc_ci(correct: np.ndarray) -> list[float]:
    return list(bootstrap_ci(len(correct), lambda i: float(correct[i].mean()), ITERS, SEED))


def _saving_ci(cost: np.ndarray, top_cost: np.ndarray) -> list[float]:
    return list(bootstrap_ci(len(cost), lambda i: float(1 - cost[i].sum() / top_cost[i].sum()), ITERS, SEED))


def _auroc_ci(score: np.ndarray, correct: np.ndarray) -> list[float]:
    return list(bootstrap_ci(len(score), lambda i: auroc(score[i], correct[i]) or 0.0, ITERS, SEED))


def analyze_run(full: dict, levels: list[str], threshold: float) -> dict:
    """One run at the frozen threshold. `full[model]` has correct, valid, cost and, for the small
    model, score. The threshold is an input and is never derived from these items."""
    small, large = dict(full[SMALL]), full[LARGE]
    n = len(small["correct"])
    sim = C.simulate([small, large], [threshold])
    esc, correct, cost = sim["escalations"][0], sim["correct"], sim["cost"]
    n_esc = int(esc.sum())
    top_cost = float(large["cost"].sum())

    singles = {}
    for m in MODELS:
        d = full[m]
        singles[m] = {"accuracy": float(d["correct"].mean()), "accuracy_ci95": _acc_ci(d["correct"]),
                      "total_cost_usd": float(d["cost"].sum()), "saving_vs_top": 1 - float(d["cost"].sum()) / top_cost,
                      "invalid_outputs": int((~d["valid"]).sum())}

    rnd = C.random_chain([small, large], [n_esc], mizan_correct=correct, base_seed=SEED)
    diff = rnd["paired_accuracy_diff"]
    point = {"accuracy": float(correct.mean()), "total_cost_usd": float(cost.sum())}
    others = {m: {k: singles[m][k] for k in ("accuracy", "total_cost_usd")} for m in MODELS}
    dominated = C.dominated_by(point, others)

    accepted = ~esc
    valid = small["valid"]
    accepted_acc = float(small["correct"][accepted].mean()) if accepted.any() else None
    random_acc = float(small["correct"][valid].mean()) if valid.any() else None  # expectation over random acceptance
    level_rows = {}
    for lv in sorted(set(levels)):
        idx = np.array([i for i, x in enumerate(levels) if x == lv])
        level_rows[lv] = {"n": int(len(idx)), "accuracy": float(correct[idx].mean()), "accuracy_ci95": _acc_ci(correct[idx]),
                          "escalation_rate": float(esc[idx].mean()), "total_cost_usd": float(cost[idx].sum()),
                          "small_slice_warning": len(idx) < SMALL_SLICE}

    return {"n": n, "threshold": threshold, "singles": singles,
            "mizan": {**point, "accuracy_ci95": _acc_ci(correct), "saving_vs_top": 1 - point["total_cost_usd"] / top_cost,
                      "saving_ci95": _saving_ci(cost, large["cost"]), "escalated_items": n_esc,
                      "achieved_escalation": float(esc.mean()), "invalid_outputs": int((~valid).sum()),
                      "not_available_margins": int(np.isposinf(small["score"]).sum())},
            "random": {"accuracy_mean": rnd["accuracy"]["mean"], "accuracy_range95": rnd["accuracy"]["ci95"],
                       "total_cost_usd_mean": rnd["total_cost_usd"]["mean"], "escalation_counts": rnd["escalation_counts"],
                       "seeds": rnd["seeds"]},
            "mizan_minus_random": {"observed": diff["observed"], "boot_mean": diff["boot_mean"], "ci95": diff["ci95"],
                                   "ci_excludes_zero": bool(diff["ci95"][0] > 0 or diff["ci95"][1] < 0)},
            "primary": classify_primary(diff["observed"], diff["ci95"]),
            "non_dominance": {"dominated_by": dominated, "on_observed_frontier": MIZAN in C.pareto_frontier({MIZAN: point, **others}),
                              "paired": {m: C.paired_bootstrap(correct, cost, full[m]["correct"], full[m]["cost"], seed=SEED)
                                         for m in MODELS}},
            "mechanism": {"auroc": auroc(small["score"], small["correct"]), "auroc_ci95_descriptive": _auroc_ci(small["score"], small["correct"]),
                          "coverage": float(accepted.mean()), "accepted_accuracy": accepted_acc,
                          "selective_risk": None if accepted_acc is None else 1 - accepted_acc,
                          "random_acceptance_accuracy": random_acc,
                          "random_acceptance_risk": None if random_acc is None else 1 - random_acc,
                          "small_error_in_escalated": float((~small["correct"][esc]).mean()) if esc.any() else None},
            "levels": level_rows}


def compare_runs(orig: dict, shuf: dict, orig_run: dict, shuf_run: dict, threshold: float, flagged: np.ndarray) -> dict:
    """Paired by question ID, in the same item order. `orig` and `shuf` map model -> arrays."""
    def route(full):
        sim = C.simulate([full[SMALL], full[LARGE]], [threshold])
        return sim["escalations"][0], sim["correct"], sim["cost"]

    e0, c0, k0 = route(orig)
    e1, c1, k1 = route(shuf)
    s0, s1 = orig[SMALL]["score"], shuf[SMALL]["score"]
    both = np.isfinite(s0) & np.isfinite(s1)
    delta = np.abs(s1[both] - s0[both])
    a0, a1 = orig_run["mechanism"]["auroc"], shuf_run["mechanism"]["auroc"]
    d0, d1 = orig_run["mizan_minus_random"]["observed"], shuf_run["mizan_minus_random"]["observed"]

    rng = np.random.default_rng(SEED)
    n = len(e0)
    boots = []
    for _ in range(ITERS):
        i = rng.integers(0, n, size=n)
        x, y = auroc(s1[i], shuf[SMALL]["correct"][i]), auroc(s0[i], orig[SMALL]["correct"][i])
        boots.append((x or 0.0) - (y or 0.0))
    lo, hi = np.percentile(boots, [2.5, 97.5])

    def transitions(a, b):
        return {"unchanged": int((a == b).sum()), "right_to_wrong": int((a & ~b).sum()), "wrong_to_right": int((~a & b).sum())}

    def flagged_accuracy(full_run):
        c = full_run
        return {"flagged": float(c[flagged].mean()) if flagged.any() else None,
                "unflagged": float(c[~flagged].mean()) if (~flagged).any() else None}

    return {"auroc_change": a1 - a0, "auroc_change_ci95_descriptive": [float(lo), float(hi)],
            "accuracy_change": float(c1.mean() - c0.mean()), "escalation_change": float(e1.mean() - e0.mean()),
            "cost_change_usd": float(k1.sum() - k0.sum()),
            "saving_change": shuf_run["mizan"]["saving_vs_top"] - orig_run["mizan"]["saving_vs_top"],
            "routing_decisions_changed": int((e0 != e1).sum()), "stayed_to_escalated": int((~e0 & e1).sum()),
            "escalated_to_stayed": int((e0 & ~e1).sum()),
            "correctness": {"mizan": transitions(c0, c1),
                            **{m: transitions(orig[m]["correct"], shuf[m]["correct"]) for m in MODELS}},
            "score_change": {"both_finite": int(both.sum()), "finite_to_infinite": int((np.isfinite(s0) & ~np.isfinite(s1)).sum()),
                             "infinite_to_finite": int((~np.isfinite(s0) & np.isfinite(s1)).sum()),
                             "both_infinite": int((~np.isfinite(s0) & ~np.isfinite(s1)).sum()),
                             "mean_abs": float(delta.mean()) if len(delta) else None,
                             "median_abs": float(np.median(delta)) if len(delta) else None},
            "mean_cost_change_usd": float((k1 - k0).mean()),
            "position_dependent": {"flagged": int(flagged.sum()), "original": flagged_accuracy(c0), "shuffled": flagged_accuracy(c1)},
            "claims": {"auroc_within_005": bool(a1 >= a0 - AUROC_MAX_DROP), "same_sign": same_sign(d0, d1),
                       "both_hold": bool(a1 >= a0 - AUROC_MAX_DROP and same_sign(d0, d1))}}


# ---------------------------------------------------------------- report


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.2f}%"


def _pts(x) -> str:
    return f"{x * 100:+.2f}"


def _ci_pct(c) -> str:
    return f"[{c[0] * 100:.2f}%, {c[1] * 100:.2f}%]"


def _ci_pts(c) -> str:
    return f"[{c[0] * 100:+.2f}, {c[1] * 100:+.2f}]"


def _num(x) -> str:
    return "n/a" if x is None else f"{x:.4f}"


def _run_section(r: dict) -> list[str]:
    m, d, mech = r["mizan"], r["mizan_minus_random"], r["mechanism"]
    L = [f"N = {r['n']}. Margin threshold {r['threshold']!r} (`margin < threshold` escalates).", "",
         "| Strategy | Accuracy | 95% CI | Total cost | Saving vs Always gpt-4.1 | Invalid outputs |", "|---|---|---|---|---|---|"]
    for name, s in r["singles"].items():
        L.append(f"| Always {name} | {_pct(s['accuracy'])} | {_ci_pct(s['accuracy_ci95'])} | ${s['total_cost_usd']:.5f} | "
                 f"{_pct(s['saving_vs_top'])} | {s['invalid_outputs']} |")
    L += [f"| **Mizan** | **{_pct(m['accuracy'])}** | {_ci_pct(m['accuracy_ci95'])} | ${m['total_cost_usd']:.5f} | "
          f"{_pct(m['saving_vs_top'])} (CI {_ci_pct(m['saving_ci95'])}) | {m['invalid_outputs']} (small model) |",
          f"| Matched Random (mean of {r['random']['seeds']} seeds) | {_pct(r['random']['accuracy_mean'])} | seed range {_ci_pct(r['random']['accuracy_range95'])} | "
          f"${r['random']['total_cost_usd_mean']:.5f} | {_pct(1 - r['random']['total_cost_usd_mean'] / r['singles'][LARGE]['total_cost_usd'])} | same as Mizan |", "",
          f"- **Mizan minus Random: {_pts(d['observed'])} points, 95% CI {_ci_pts(d['ci95'])}. Primary result: {r['primary']}.**",
          f"- Margin AUROC for gpt-4o-mini correctness: {_num(mech['auroc'])} (descriptive 95% CI [{_num(mech['auroc_ci95_descriptive'][0])}, {_num(mech['auroc_ci95_descriptive'][1])}]).",
          f"- Escalation: target on Dev 30.00%, achieved {_pct(m['achieved_escalation'])} ({m['escalated_items']} of {r['n']}). The target is not enforced on this set.",
          f"- `not_available` margins (scored +inf, never escalated by margin): {m['not_available_margins']}.",
          f"- Selective risk / coverage: coverage {_pct(mech['coverage'])}; risk on accepted items {_pct(mech['selective_risk'])} "
          f"(accuracy {_pct(mech['accepted_accuracy'])}), vs random acceptance risk {_pct(mech['random_acceptance_risk'])} "
          f"(accuracy {_pct(mech['random_acceptance_accuracy'])}).",
          f"- gpt-4o-mini error rate inside the escalated set: {_pct(mech['small_error_in_escalated'])}.", "",
          f"Non-dominance: dominated by {', '.join(r['non_dominance']['dominated_by']) or 'no single model'}; "
          f"on the observed frontier of the four measured points: {'yes' if r['non_dominance']['on_observed_frontier'] else 'no'}.", "",
          "| Mizan minus | Accuracy (points) | 95% CI | Cost (USD) | 95% CI |", "|---|---|---|---|---|"]
    for name, b in r["non_dominance"]["paired"].items():
        a, c = b["accuracy_diff"], b["cost_diff"]
        L.append(f"| Always {name} | {_pts(a['observed'])} | {_ci_pts(a['ci95'])} | {c['observed']:+.5f} | [{c['ci95'][0]:+.5f}, {c['ci95'][1]:+.5f}] |")
    L += ["", "Education level slices (descriptive only, no claim):", "",
          "| Level | N | Mizan accuracy | 95% CI | Escalation | Cost | Warning |", "|---|---|---|---|---|---|---|"]
    for lv, s in r["levels"].items():
        L.append(f"| {lv} | {s['n']} | {_pct(s['accuracy'])} | {_ci_pct(s['accuracy_ci95'])} | {_pct(s['escalation_rate'])} | "
                 f"${s['total_cost_usd']:.5f} | {'small slice (N < 30)' if s['small_slice_warning'] else ''} |")
    return L


def report_md(res: dict) -> str:
    o, s, c, ops, pre = res["original"], res["perturbation"], res["comparison"], res["operations"], res["preflight"]
    cl = c["claims"]
    t = c["correctness"]
    pd_ = c["position_dependent"]
    sc = c["score_change"]
    man = res["perturbation_manifest"]
    L = ["# MIZAN held-out report", "",
         f"Generated: {res['generated_at']}. All numbers come from `artifacts/heldout_results.json`.", "",
         f"**Decision: {res['decision']}** {res['decision_reason']}", "",
         "## 1. Original held-out", ""] + _run_section(o)
    L += ["", "## 2. Option-order perturbation", "",
          "This is not a new held-out set, unseen questions or out-of-domain data. It is the same 500 questions with options reordered.",
          f"Seed {man['seed']}. Items whose displayed order stayed identical: {man['stayed_identical']}. "
          f"Items whose correct letter changed: {man['answer_letter_changed']}.", ""] + _run_section(s)
    L += ["", "### Change, shuffled minus original", "",
          f"- AUROC: {c['auroc_change']:+.4f} (descriptive 95% CI [{c['auroc_change_ci95_descriptive'][0]:+.4f}, {c['auroc_change_ci95_descriptive'][1]:+.4f}])",
          f"- Mizan accuracy: {_pts(c['accuracy_change'])} points",
          f"- Escalation rate: {_pts(c['escalation_change'])} points",
          f"- Total cost: {c['cost_change_usd']:+.5f} USD ({c['mean_cost_change_usd']:+.7f} USD per item)",
          f"- Saving vs Always gpt-4.1: {_pts(c['saving_change'])} points",
          f"- Routing decisions changed: {c['routing_decisions_changed']} of {o['n']} ({c['stayed_to_escalated']} newly escalated, {c['escalated_to_stayed']} no longer escalated)",
          "", "### Paired comparison by question ID", "",
          "| Answerer | Same correctness | Right to wrong | Wrong to right |", "|---|---|---|---|",
          f"| Mizan | {t['mizan']['unchanged']} | {t['mizan']['right_to_wrong']} | {t['mizan']['wrong_to_right']} |"]
    L += [f"| Always {m} | {t[m]['unchanged']} | {t[m]['right_to_wrong']} | {t[m]['wrong_to_right']} |" for m in MODELS]
    L += ["", f"Routing score change: mean absolute {_num(sc['mean_abs'])}, median absolute {_num(sc['median_abs'])} over {sc['both_finite']} items finite in both runs. "
          f"Finite to infinite: {sc['finite_to_infinite']}. Infinite to finite: {sc['infinite_to_finite']}. Infinite in both: {sc['both_infinite']}.", "",
          f"Items with an option referring to other options (flagged, never removed): {pd_['flagged']}. "
          f"Mizan accuracy, original: flagged {_pct(pd_['original']['flagged'])}, unflagged {_pct(pd_['original']['unflagged'])}. "
          f"Shuffled: flagged {_pct(pd_['shuffled']['flagged'])}, unflagged {_pct(pd_['shuffled']['unflagged'])}.", "",
          "### Registered robustness claim", "",
          f"- AUROC_shuffled >= AUROC_original - 0.05: **{'holds' if cl['auroc_within_005'] else 'fails'}** ({_num(s['mechanism']['auroc'])} vs {_num(o['mechanism']['auroc'])}).",
          f"- Mizan minus Random keeps the same sign: **{'holds' if cl['same_sign'] else 'fails'}** ({_pts(o['mizan_minus_random']['observed'])} vs {_pts(s['mizan_minus_random']['observed'])}).",
          "", "## 3. Integrity and operations", "",
          f"- Approved preregistration commit: `{pre['approved_commit']}`",
          f"- Commit used for the run: `{pre['head']}` (adds new files only; list below)",
          f"- Files added after the approved commit: {', '.join('`' + f + '`' for f in pre['added_since_approved'])}",
          f"- `docs/decisions.md` SHA-256: `{pre['decisions_sha256']}`, unchanged at the end: {ops['decisions_unchanged']}",
          f"- Model snapshots returned: {res['snapshots']}",
          f"- API calls: {ops['calls_ok']} succeeded of {ops['attempts']} attempts ({ops['calls_by_run']})",
          f"- Cache hits/misses: {ops['cache_summary']}",
          f"- Errors and retries: {ops['failed_attempts']} failed attempts, {ops['errors']}. A failed attempt may be billed by the provider but is not in the ledger.",
          f"- Unique response IDs shared between the two runs: {ops['response_ids_shared']}. Prompt-hash mismatches against the items: {ops['prompt_hash_mismatches']}.",
          f"- Cost of this experiment: original ${ops['run_cost']['heldout']:.5f}, perturbation ${ops['run_cost']['perturbation']:.5f}; "
          f"ledger delta ${ops['ledger_delta']:.5f}",
          f"- Actual cumulative experiment cost: ${ops['ledger_total']:.5f} of ${ops['budget']:.2f}",
          f"- Settings changed after held-out was opened: {'none' if ops['settings_unchanged'] else 'YES, see below'}. "
          f"Tracked changes at the end: {ops['final_status'] or 'none'}.", "",
          "Differences from the preregistration text, all reported rather than silently applied:", ""]
    L += [f"- {x}" for x in res["deviations"]]
    L += ["", "## 4. Decision", "", f"**{res['decision']}** {res['decision_reason']}", ""]
    return "\n".join(L)


def finite(x):
    """Strict JSON has no Infinity."""
    if isinstance(x, dict):
        return {k: finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [finite(v) for v in x]
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(x) else ("-inf" if x < 0 else "inf")
    if isinstance(x, (np.integer, np.bool_)):
        return x.item()
    return x
