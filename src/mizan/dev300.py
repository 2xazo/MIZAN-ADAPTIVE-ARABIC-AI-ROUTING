"""Dev 300 confirmation: tune on the first 100 items, confirm unchanged on the new 200.

Works on per-model arrays, so it is fully offline. Report numbers are generated from the results
dict and are never typed by hand. Latency is kept raw and is deliberately not summarized.
"""
from __future__ import annotations

import math
import time

import numpy as np

from . import cascade as C
from .analysis import pick_signal, signal_report

CHEAP, MID, TOP = "gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1"
EXPLORATION_N = 100
SINGLES = [[CHEAP], [MID], [TOP]]
PAIRS = [[CHEAP, MID], [CHEAP, TOP], [MID, TOP]]
CASCADE = [CHEAP, MID, TOP]
MAX_LOSS_SECONDARY = 0.02


def name_of(chain: list[str]) -> str:
    return " -> ".join(chain)


def _subset(m: dict, idx: np.ndarray, signal: str | None) -> dict:
    n = len(idx)
    return {"correct": m["correct"][idx], "valid": m["valid"][idx], "cost": m["cost"][idx],
            "score": m["scores"][signal][idx] if signal else np.zeros(n)}


def _models(chain: list[str], full: dict, signals: dict, idx: np.ndarray) -> list[dict]:
    return [_subset(full[m], idx, signals.get(m)) for m in chain]


def choose_signals(full: dict, idx: np.ndarray) -> dict:
    """Signal for each routing stage, chosen on the exploration items only."""
    out = {}
    for model in (CHEAP, MID):
        m = full[model]
        records = [{"small": {"normalized_complete": bool(m["normalized_complete"][i]),
                              "margin": "not_available" if m["margin_missing"][i] else 0.0,
                              "valid": bool(m["valid"][i]),
                              "raw_logprob": float(m["scores"]["raw_logprob"][i]),
                              "normalized": float(m["scores"]["normalized"][i])}} for i in idx]
        # signal_report scores records itself, so give it the already-computed margin too.
        for r, i in zip(records, idx):
            if not m["margin_missing"][i]:
                r["small"]["margin"] = float(m["scores"]["margin"][i])
        out[model] = pick_signal(signal_report(records, {"sc": m["correct"][idx], "valid": m["valid"][idx]}))
    return out


def signal_table(full: dict, signals: dict, first: np.ndarray, rest: np.ndarray) -> dict:
    out = {}
    for model, sig in signals.items():
        m = full[model]
        row = {"signal": sig, "stage": 1 if model == CHEAP else 2}
        for label, idx in (("first_100", first), ("confirmation_200", rest)):
            row[label] = C.signal_stats(m["correct"][idx], m["valid"][idx], m["scores"][sig][idx], m["confidence"][idx])
            row[label]["auroc_all_signals"] = {s: C.auroc(m["scores"][s][idx], m["correct"][idx]) for s in m["scores"]}
        a, b = row["first_100"]["auroc"], row["confirmation_200"]["auroc"]
        row["auroc_drop"] = None if a is None or b is None else a - b
        row["overconfidence_change"] = row["confirmation_200"]["overconfidence"] - row["first_100"]["overconfidence"]
        out[model] = row
    return out


def _evaluate(chain: list[str], full: dict, signals: dict, thresholds: list[float], idx: np.ndarray, seed: int) -> dict:
    models = _models(chain, full, signals, idx)
    sim = C.simulate(models, thresholds)
    out = C.summarize(sim, chain)
    out["_correct"], out["_cost"] = sim["correct"], sim["cost"]
    if len(chain) > 1:
        out["escalated_items"] = [int(e.sum()) for e in sim["escalations"][:-1]]
        out["random"] = C.random_chain(models, out["escalated_items"], mizan_correct=sim["correct"], base_seed=seed)
        out["oracle"] = C.oracle_chain(models)
    return out


def _tune(chain: list[str], full: dict, signals: dict, idx: np.ndarray, objective: str) -> dict | None:
    models = _models(chain, full, signals, idx)
    points = C.grid_points(models)
    if objective == "primary":
        limit = float(full[MID]["cost"][idx].sum())
        return C.choose_point(models, points, "primary", max_cost=limit)
    floor = float(full[TOP]["correct"][idx].mean()) - MAX_LOSS_SECONDARY
    return C.choose_point(models, points, "secondary", min_accuracy=floor)


def _public(ev: dict) -> dict:
    return {k: v for k, v in ev.items() if not k.startswith("_")}


def _is_degenerate(chain: list[str], ev: dict) -> bool:
    """A routed design that never escalates IS its first model, not a separate design."""
    return len(chain) > 1 and ev["escalated_items"][0] == 0


def _collapses_to_pair(chain: list[str], ev: dict) -> bool:
    return len(chain) == 3 and ev["escalated_items"][0] > 0 and ev["escalated_items"][1] == 0


def verdict(chain: list[str], ev: dict, singles_200: dict, mid_cost: float) -> dict:
    """Binding test on the confirmation items. A routed design must not be dominated by a single
    model, must stay within the cost limit, must escalate, and must beat matched Random's mean."""
    others = {k: v for k, v in singles_200.items() if k != name_of(chain)}
    by = C.dominated_by(ev, others)
    cost_ok = ev["total_cost_usd"] <= mid_cost + 1e-12
    degenerate = _is_degenerate(chain, ev)
    routed = len(chain) > 1
    beats = bool(routed and ev["accuracy"] > ev["random"]["accuracy"]["mean"] + 1e-9)
    return {"dominated_by": by, "cost_within_limit": cost_ok, "degenerate_no_escalation": degenerate,
            "collapses_to_pair": _collapses_to_pair(chain, ev), "beats_random": beats,
            "passes": routed and not by and cost_ok and not degenerate and beats}


def analyze_dev(full: dict, ids: list[str], seed: int = 0) -> dict:
    n = len(ids)
    first = np.arange(EXPLORATION_N)
    rest = np.arange(EXPLORATION_N, n)
    everything = np.arange(n)
    signals = choose_signals(full, first)

    designs, internals = {}, {}
    for chain in SINGLES + PAIRS + [CASCADE]:
        name = name_of(chain)
        kind = "single" if len(chain) == 1 else "pair" if len(chain) == 2 else "cascade"
        entry = {"chain": chain, "kind": kind,
                 "signals": {m: signals[m] for m in chain[:-1]}, "objectives": {}}
        for objective in ("primary", "secondary"):
            point = _tune(chain, full, signals, first, objective) if len(chain) > 1 else {"target": [], "thresholds": []}
            if point is None:
                entry["objectives"][objective] = {"feasible_on_first_100": False}
                continue
            evals = {label: _evaluate(chain, full, signals, point["thresholds"], idx, seed)
                     for label, idx in (("first_100", first), ("confirmation_200", rest), ("combined_300", everything))}
            entry["objectives"][objective] = {"feasible_on_first_100": True, "target_escalation": point["target"],
                                              "thresholds": point["thresholds"],
                                              **{k: _public(v) for k, v in evals.items()}}
            internals[(name, objective)] = evals
        designs[name] = entry

    # Binding test: primary operating point, confirmation items only.
    singles_200 = {name_of(c): designs[name_of(c)]["objectives"]["primary"]["confirmation_200"] for c in SINGLES}
    mid_cost = singles_200[MID]["total_cost_usd"]
    for name, entry in designs.items():
        block = entry["objectives"]["primary"]
        if not block["feasible_on_first_100"]:
            entry["verdict"] = {"passes": False, "reason": "infeasible on first 100"}
            continue
        entry["verdict"] = verdict(entry["chain"], block["confirmation_200"], singles_200, mid_cost)

    points_200 = {k: {"accuracy": v["objectives"]["primary"]["confirmation_200"]["accuracy"],
                      "total_cost_usd": v["objectives"]["primary"]["confirmation_200"]["total_cost_usd"]}
                  for k, v in designs.items() if v["objectives"]["primary"]["feasible_on_first_100"]}
    frontier = C.pareto_frontier(points_200)

    def rank(names):
        return sorted(names, key=lambda k: (-points_200[k]["accuracy"], points_200[k]["total_cost_usd"]))

    passing = [k for k, v in designs.items() if v["verdict"]["passes"]]
    passing_pairs = [k for k in passing if designs[k]["kind"] == "pair"]
    usable_pairs = [name_of(c) for c in PAIRS if (name_of(c), "primary") in internals
                    and not designs[name_of(c)]["verdict"]["degenerate_no_escalation"]]
    best_pair = (rank(passing_pairs) or rank(usable_pairs) or [None])[0]

    def arrays(k):
        ev = internals[(k, "primary")]["confirmation_200"]
        return ev["_correct"], ev["_cost"]

    cascade_name = name_of(CASCADE)
    comparison = None
    cascade_usable = (cascade_name, "primary") in internals
    if cascade_usable and best_pair:
        boot = C.paired_bootstrap(*arrays(cascade_name), *arrays(best_pair), seed=seed)
        beats = boot["accuracy_diff"]["observed"] > 1e-9
        significant = boot["accuracy_diff"]["ci_excludes_zero"]
        comparison = {"cascade": cascade_name, "best_pair": best_pair, "paired_bootstrap": boot,
                      "beats_best_pair_on_200": beats, "accuracy_ci_excludes_zero": significant,
                      "cascade_passes_binding_test": designs[cascade_name]["verdict"]["passes"],
                      "accepted": bool(beats and significant and designs[cascade_name]["verdict"]["passes"])}

    # Simplest design wins unless the cascade clears every acceptance condition.
    chosen = None
    if comparison and comparison["accepted"]:
        chosen = cascade_name
    elif passing_pairs:
        chosen = rank(passing_pairs)[0]

    vs_singles, warnings = {}, []
    if chosen:
        for single in SINGLES:
            s = name_of(single)
            ev = internals[(s, "primary")]["confirmation_200"]
            vs_singles[s] = C.paired_bootstrap(*arrays(chosen), ev["_correct"], ev["_cost"], seed=seed)
        for single in (MID, TOP):
            if not vs_singles[single]["accuracy_diff"]["ci_excludes_zero"]:
                warnings.append(f"Accuracy vs Always {single} is statistically tied on the 200 (CI includes zero).")
        r = designs[chosen]["objectives"]["primary"]["confirmation_200"]["random"]["paired_accuracy_diff"]
        if r["ci95"][0] <= 0 <= r["ci95"][1]:
            warnings.append("The gain over matched Random has a 95% CI that includes zero.")

    decision = "GO to held-out" if chosen else "NO-GO"
    if chosen:
        why = f"{chosen} passes non-dominance, the cost limit and beats matched Random on the confirmation 200."
    else:
        why = "No routed design passes: each is dominated, breaks the cost limit, never escalates, or does not beat matched Random."

    frozen = None
    if chosen:
        chain = designs[chosen]["chain"]
        point = _tune(chain, full, signals, everything, "primary")
        ev = _evaluate(chain, full, signals, point["thresholds"], everything, seed)
        frozen = {"architecture": chosen, "signals": designs[chosen]["signals"],
                  "target_escalation": point["target"], "thresholds": point["thresholds"],
                  "retuned_on": "all 300 (in-sample, exploratory)", "in_sample_on_300": _public(ev)}

    return {"n": n, "exploration_ids": ids[:EXPLORATION_N], "confirmation_ids": ids[EXPLORATION_N:],
            "signals_chosen_on_first_100": signals, "signal_table": signal_table(full, signals, first, rest),
            "grid": list(C.ESCALATION_GRID), "designs": designs, "pareto_frontier_on_200": frontier,
            "pareto_points_on_200": points_200, "cascade_vs_best_pair": comparison,
            "chosen_design": chosen, "chosen_vs_singles": vs_singles, "warnings": warnings,
            "decision": decision, "decision_reason": why, "frozen": frozen}


# ---------------------------------------------------------------- report


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _usd(x):
    return "n/a" if x is None else f"${x:.5f}"


def _num(x):
    return "n/a" if x is None else f"{x:.4f}"


def _thr(x):
    if isinstance(x, str):
        return x
    return "-inf" if math.isinf(x) and x < 0 else f"{x:.4f}"


def _rates(values):
    return " / ".join(_pct(v) for v in values) if values else "none"


def _set_table(res: dict, label: str, objective: str = "primary") -> list[str]:
    L = ["| Design | Accuracy | Cost | Target escalation | Achieved escalation | Random accuracy (mean) | Oracle accuracy |",
         "|---|---|---|---|---|---|---|"]
    for name, d in res["designs"].items():
        b = d["objectives"][objective]
        if not b["feasible_on_first_100"]:
            L.append(f"| {name} | infeasible on first 100 |  |  |  |  |  |")
            continue
        e = b[label]
        rnd = e.get("random")
        orc = e.get("oracle")
        L.append(f"| {name} | {_pct(e['accuracy'])} | {_usd(e['total_cost_usd'])} | {_rates(b['target_escalation'])} | "
                 f"{_rates(e['achieved_escalation'])} | {_pct(rnd['accuracy']['mean']) if rnd else '-'} | "
                 f"{_pct(orc['accuracy']) if orc else '-'} |")
    return L


def _boot_lines(b: dict) -> list[str]:
    a, c = b["accuracy_diff"], b["cost_diff"]
    return [f"- Accuracy difference: {a['observed'] * 100:+.1f} points, 95% CI "
            f"[{a['ci95'][0] * 100:+.1f}, {a['ci95'][1] * 100:+.1f}], excludes zero: {a['ci_excludes_zero']}",
            f"- Cost difference: {c['observed']:+.5f} USD, 95% CI [{c['ci95'][0]:+.5f}, {c['ci95'][1]:+.5f}], "
            f"excludes zero: {c['ci_excludes_zero']}"]


def report_md(res: dict, spent: float, budget: float) -> str:
    D = res["designs"]
    L = ["# MIZAN Dev 300 confirmation report", "",
         "**Superseded on 2026-10-30.** All of Dev 300 is now exploratory, and this report's decision and frozen point "
         "no longer apply. See `docs/decisions.md` and `artifacts/dev300_curve.md`.", "",
         f"Generated: {res['generated_at']}  ",
         f"Items: first 100 (exploration), next {res['n'] - EXPLORATION_N} (confirmation). Held-out was not used.", "",
         f"**Decision: {res['decision']}.** {res['decision_reason']}", ""]
    if res["warnings"]:
        L += ["**Warnings:**"] + [f"- {w}" for w in res["warnings"]] + [""]
    L += ["Thresholds and the operating point were chosen on the first 100 and applied unchanged to the 200. "
          "Primary objective: highest accuracy with cost at or below Always gpt-4.1-mini.", ""]

    L += ["## 1. First-100 results (exploration, optimistic)", ""] + _set_table(res, "first_100") + [""]
    L += ["## 2. Confirmation-200 results (binding)", ""] + _set_table(res, "confirmation_200") + [""]
    L += ["## 3. Combined 300 results (exploratory, not confirmatory)", ""] + _set_table(res, "combined_300") + [""]

    L += ["## 4. Accuracy and cost: every single model, pair and the cascade", "",
          "| Design | Kind | Acc 100 | Cost 100 | Acc 200 | Cost 200 | Acc 300 | Cost 300 |", "|---|---|---|---|---|---|---|---|"]
    for name, d in D.items():
        b = d["objectives"]["primary"]
        if b["feasible_on_first_100"]:
            L.append(f"| {name} | {d['kind']} | " + " | ".join(
                f"{_pct(b[s]['accuracy'])} | {_usd(b[s]['total_cost_usd'])}" for s in ("first_100", "confirmation_200", "combined_300")) + " |")
    L += ["", "Secondary objective (report only): lowest cost with accuracy at or above Always gpt-4.1 minus 2 points, tuned on the first 100.", "",
          "| Design | Target escalation | Acc 100 | Cost 100 | Acc 200 | Cost 200 |", "|---|---|---|---|---|---|"]
    for name, d in D.items():
        if d["kind"] == "single":
            continue
        b = d["objectives"]["secondary"]
        if not b["feasible_on_first_100"]:
            L.append(f"| {name} | infeasible on first 100 |  |  |  |  |")
        else:
            L.append(f"| {name} | {_rates(b['target_escalation'])} | {_pct(b['first_100']['accuracy'])} | {_usd(b['first_100']['total_cost_usd'])} | "
                     f"{_pct(b['confirmation_200']['accuracy'])} | {_usd(b['confirmation_200']['total_cost_usd'])} |")

    L += ["", "## 5. Pareto frontier and non-dominance (confirmation 200)", "",
          "Frontier: " + ", ".join(f"`{n}`" for n in res["pareto_frontier_on_200"]), "",
          "| Design | Dominated by a single model | Cost within limit | Never escalates | Beats matched Random | Passes |", "|---|---|---|---|---|---|"]
    for name, d in D.items():
        v = d["verdict"]
        if d["kind"] == "single":
            L.append(f"| {name} | {', '.join(v.get('dominated_by', [])) or 'no'} | {v.get('cost_within_limit')} | - | - | baseline |")
        else:
            L.append(f"| {name} | {', '.join(v.get('dominated_by', [])) or 'no'} | {v.get('cost_within_limit')} | "
                     f"{v.get('degenerate_no_escalation')} | {v.get('beats_random')} | {v['passes']} |")

    L += ["", "## 6. AUROC per stage", "",
          "| Stage | Model | Signal | AUROC 100 | AUROC 200 | Drop | Overconfidence 100 | Overconfidence 200 |", "|---|---|---|---|---|---|---|---|"]
    for model, r in res["signal_table"].items():
        a, b = r["first_100"], r["confirmation_200"]
        L.append(f"| {r['stage']} | {model} | {r['signal']} | {_num(a['auroc'])} | {_num(b['auroc'])} | {_num(r['auroc_drop'])} | "
                 f"{_pct(a['overconfidence'])} | {_pct(b['overconfidence'])} |")
    L += ["", "Overconfidence is mean p(chosen answer) minus accuracy. Signals were not changed after seeing the 200. All signals, for information:", "",
          "| Model | Set | raw_logprob | normalized | margin |", "|---|---|---|---|---|"]
    for model, r in res["signal_table"].items():
        for label in ("first_100", "confirmation_200"):
            s = r[label]["auroc_all_signals"]
            L.append(f"| {model} | {label} | {_num(s['raw_logprob'])} | {_num(s['normalized'])} | {_num(s['margin'])} |")

    L += ["", "## 7. Target vs achieved thresholds and escalation rates", "",
          "Stage-2 rates are conditional: a share of the items that reached stage 2.", "",
          "| Design | Thresholds | Target | Achieved 100 | Achieved 200 | Achieved 300 |", "|---|---|---|---|---|---|"]
    for name, d in D.items():
        b = d["objectives"]["primary"]
        if d["kind"] != "single" and b["feasible_on_first_100"]:
            L.append(f"| {name} | {' / '.join(_thr(t) for t in b['thresholds'])} | {_rates(b['target_escalation'])} | "
                     f"{_rates(b['first_100']['achieved_escalation'])} | {_rates(b['confirmation_200']['achieved_escalation'])} | "
                     f"{_rates(b['combined_300']['achieved_escalation'])} |")

    L += ["", "## 8. Stop distribution (share stopped at each model)", "", "| Design | Set | Stopped at |", "|---|---|---|"]
    for name, d in D.items():
        b = d["objectives"]["primary"]
        if d["kind"] != "single" and b["feasible_on_first_100"]:
            for label in ("first_100", "confirmation_200"):
                L.append(f"| {name} | {label} | " + ", ".join(f"{m}: {_pct(v)}" for m, v in b[label]["stopped_at"].items()) + " |")

    L += ["", "## 9. Conditionally matched Random (1000 seeds)", "",
          "Binding on the 200: a design must have higher accuracy than the Random mean. The paired difference resamples the same items for both methods.", "",
          "| Design | Set | Mizan accuracy | Random mean | Random 95% interval | Paired difference (points) | Paired 95% CI (points) | Mizan cost | Random cost (mean) |", "|---|---|---|---|---|---|---|---|---|"]
    for name, d in D.items():
        b = d["objectives"]["primary"]
        if d["kind"] != "single" and b["feasible_on_first_100"]:
            for label in ("first_100", "confirmation_200"):
                e = b[label]
                r = e["random"]
                p = r["paired_accuracy_diff"]
                L.append(f"| {name} | {label} | {_pct(e['accuracy'])} | {_pct(r['accuracy']['mean'])} | "
                         f"[{_pct(r['accuracy']['ci95'][0])}, {_pct(r['accuracy']['ci95'][1])}] | {p['observed'] * 100:+.1f} | "
                         f"[{p['ci95'][0] * 100:+.1f}, {p['ci95'][1] * 100:+.1f}] | {_usd(e['total_cost_usd'])} | {_usd(r['total_cost_usd']['mean'])} |")

    L += ["", "## 10. Oracle (uses ground truth: theoretical upper bound only)", "", "| Design | Set | Accuracy | Cost | Stopped at each model |", "|---|---|---|---|---|"]
    for name, d in D.items():
        b = d["objectives"]["primary"]
        if d["kind"] != "single" and b["feasible_on_first_100"]:
            for label in ("first_100", "confirmation_200"):
                o = b[label]["oracle"]
                L.append(f"| {name} | {label} | {_pct(o['accuracy'])} | {_usd(o['total_cost_usd'])} | {_rates(o['stopped_at'])} |")

    L += ["", "## 11. Paired bootstrap (1000 iterations, confirmation 200)", ""]
    c = res["cascade_vs_best_pair"]
    if c:
        L += [f"Cascade minus best pair (`{c['best_pair']}`):"] + _boot_lines(c["paired_bootstrap"]) + [""]
    else:
        L += ["No cascade vs pair comparison was possible.", ""]
    for s, b in res["chosen_vs_singles"].items():
        L += [f"Chosen design minus Always {s}:"] + _boot_lines(b) + [""]

    L += ["## 12. Actual cumulative cost", "", f"${spent:.4f} of ${budget:.2f} (recorded in the cost ledger).", ""]

    L += ["## 13. Best simple non-dominated design", ""]
    if res["chosen_design"]:
        e = D[res["chosen_design"]]["objectives"]["primary"]["confirmation_200"]
        L += [f"`{res['chosen_design']}`: accuracy {_pct(e['accuracy'])}, cost {_usd(e['total_cost_usd'])} on the 200.", ""]
    else:
        L += ["None. No routed design passed the binding test.", ""]

    L += ["## 14. Does the cascade add a meaningful improvement?", ""]
    if c:
        L += [f"{'Yes' if c['accepted'] else 'No'}. Beats best pair on the 200: {c['beats_best_pair_on_200']}. "
              f"Accuracy CI excludes zero: {c['accuracy_ci_excludes_zero']}. Passes binding test: {c['cascade_passes_binding_test']}.", ""]
    else:
        L += ["Not established: no comparison was possible.", ""]

    L += ["## 15. Decision", "", f"**{res['decision']}.** {res['decision_reason']}", ""]
    if res["frozen"]:
        f = res["frozen"]
        L += [f"Frozen before held-out: `{f['architecture']}`, signals {f['signals']}, thresholds "
              f"{[_thr(t) for t in f['thresholds']]}, retuned on {f['retuned_on']}. "
              f"In-sample accuracy {_pct(f['in_sample_on_300']['accuracy'])}, cost {_usd(f['in_sample_on_300']['total_cost_usd'])}. "
              "These in-sample numbers are not a performance claim.", ""]
    return "\n".join(L) + "\n"


def stamp(res: dict) -> dict:
    res["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return res
