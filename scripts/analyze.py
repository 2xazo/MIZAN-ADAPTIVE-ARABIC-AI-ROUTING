"""OFFLINE, no API: recompute every number from cached responses.

    python scripts/analyze.py --pairs gpt-4.1-mini:gpt-4.1 [gpt-4o-mini:gpt-4.1 ...] --n 100

Tunes signal + threshold on DEV only, picks the first pair that passes GO (in the order given),
and writes the single source of truth: artifacts/results.json (+ a readable gonogo_report.md).
With --heldout, applies the frozen Dev choices to held-out (no tuning on held-out).
"""
import _common  # noqa: F401
import argparse
import json
import time

from mizan.analysis import analyze_pair
from mizan.config import DEV_FILE, HELDOUT_FILE, LEDGER_FILE, REPORT_FILE, RESULTS_FILE, experiment, prices
from mizan.costs import Ledger
from mizan.data import read_jsonl
from mizan.runner import load_records


def fmt(x, pct=False):
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%" if pct else f"{x:.4f}"


def report_md(res: dict) -> str:
    d = res["dev"]
    L = [f"# MIZAN Go/No-Go report", "",
         f"Generated: {res['generated_at']}  ",
         f"Pairs tried on Dev: {res['pairs_tried']}  ",
         f"Spent so far: ${res['spent_usd']:.4f} of ${res['budget_experiments_usd']:.2f}", "",
         f"## Selected pair: {d['pair']['small']} -> {d['pair']['large']}  (Dev n={d['n']})", "",
         f"**Decision: {d['decision']}**", "",
         "> Threshold and signal were tuned AND measured on the same Dev items: optimistic estimate.", "",
         "| Strategy | Accuracy | Saving vs Large | Escalation | Cost (USD) | p95 latency (s) |",
         "|---|---|---|---|---|---|"]
    for k, s in d["strategies"].items():
        if s:
            L.append(f"| {k} | {fmt(s['accuracy'], True)} | {fmt(s['saving_vs_large'], True)} | "
                     f"{fmt(s['escalation_rate'], True)} | {s['total_cost_usd']:.5f} | {s['latency_p95_s']:.2f} |")
    L += ["", f"Gap Large-Small: {d['gap_points']:.1f} points. Invalid small outputs: {d['invalid_small_outputs']}.",
          f"Selected signal: `{d['selected_signal']}`, threshold: {d['threshold']}", "",
          "| Signal | AUROC | Coverage of valid items |", "|---|---|---|"]
    for k, v in d["signals"].items():
        L.append(f"| {k} | {fmt(v['auroc'])} | {fmt(v['coverage_of_valid'], True)} |")
    L += ["", "| GO check | Pass |", "|---|---|"] + [f"| {k} | {v} |" for k, v in d["go_checks"].items()]
    L += ["", f"Tokens: {d['tokens']}"]
    if res.get("other_pairs"):
        L += ["", "## Other pairs tried"] + [f"- {p['pair']['small']} -> {p['pair']['large']}: {p['decision']}"
                                            for p in res["other_pairs"]]
    if res.get("heldout"):
        h = res["heldout"]
        L += ["", f"## Held-out (n={h['n']}, frozen Dev threshold)"]
        for k, s in h["strategies"].items():
            if s:
                L.append(f"- {k}: acc {fmt(s['accuracy'], True)}, saving {fmt(s['saving_vs_large'], True)}, "
                         f"escalation {fmt(s['escalation_rate'], True)}")
        if h.get("bootstrap_95ci"):
            L.append(f"- 95% CI: {h['bootstrap_95ci']}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", required=True, help="small:large ...")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--heldout-n", type=int, default=500)
    args = ap.parse_args()
    cfg, pr = experiment(), prices()
    crit = cfg["go_criteria"]
    dev = read_jsonl(DEV_FILE)[: args.n]

    results, chosen = [], None
    for pair in args.pairs:
        small, large = pair.split(":")
        recs = load_records(dev, small, large, pr)
        if not recs:
            print(f"{pair}: no cached records, skipped")
            continue
        r = analyze_pair(recs, small, large, crit, seed=cfg["seed"])
        results.append(r)
        print(f"{pair}: n={r['n']} decision={r['decision']}")
        if r["decision"] == "GO":
            chosen = r
            break  # stop searching as soon as a pair passes
    if not results:
        raise SystemExit("Nothing to analyze: run scripts/run_eval.py first.")
    chosen = chosen or results[-1]

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": cfg["data"]["dataset"], "seed": cfg["seed"],
        "pairs_tried": len(results),
        "spent_usd": Ledger(LEDGER_FILE, cfg["budget"]["experiments_usd"]).spent(),
        "budget_experiments_usd": cfg["budget"]["experiments_usd"],
        "prices_verified": pr.get("verified"), "prices_verified_on": pr.get("verified_on"),
        "dev": chosen,
        "other_pairs": [r for r in results if r is not chosen],
    }
    if args.heldout:
        held = read_jsonl(HELDOUT_FILE)[: args.heldout_n]
        recs = load_records(held, chosen["pair"]["small"], chosen["pair"]["large"], pr)
        out["heldout"] = analyze_pair(recs, chosen["pair"]["small"], chosen["pair"]["large"], crit,
                                      threshold=chosen["threshold"], signal=chosen["selected_signal"],
                                      bootstrap_iters=1000, seed=cfg["seed"])
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    REPORT_FILE.write_text(report_md(out), encoding="utf-8")
    print(f"-> {RESULTS_FILE.name}, {REPORT_FILE.name}")


if __name__ == "__main__":
    main()
