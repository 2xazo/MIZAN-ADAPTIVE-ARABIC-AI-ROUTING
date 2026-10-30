"""OFFLINE, no API: analysis of the original held-out and option-order runs at the frozen point.

    python scripts/analyze_heldout.py

Stops, writing nothing, if any response is missing or any integrity check fails. Writes
artifacts/heldout_results.json and artifacts/heldout_report.md.
"""
import _common  # noqa: F401
import json
import time
from collections import Counter

import numpy as np

import run_heldout as RH
from mizan import client, heldout as H
from mizan.config import ARTIFACTS_DIR, CACHE_DIR, HELDOUT_FILE, LEDGER_FILE, PERTURBATION_CACHE_DIR, PERTURBATION_FILE, ROOT, experiment, prices
from mizan.costs import Ledger
from mizan.data import read_jsonl
from mizan.prompts import build_messages
from mizan.routing import score
from mizan.runner import load_side

RESULTS = ARTIFACTS_DIR / "heldout_results.json"
REPORT = ARTIFACTS_DIR / "heldout_report.md"
DEVIATIONS = [
    "Section 12 places the analysis of the original run before the perturbation run. The coordinator's approval orders the analysis after both runs, "
    "and that order was followed. No held-out result was analyzed before the perturbation run finished.",
    "Section 12 requires the analysis script to be committed before step 1. That commit comes after the approved commit and adds new files only.",
    "Section 12 names `scripts/run_eval.py` directly. `scripts/run_heldout.py` calls its `main()` with exactly those arguments, adding attempt and cache logs.",
    "The optional held-out curve (section 9) was not computed, so no other operating point was ever visible.",
    "AUROC confidence intervals and the GO mapping in `src/mizan/heldout.py` were added by the executor before any held-out call. The intervals are descriptive.",
]


def load_model(items, model, pr, cache_dir):
    sides = [load_side(it, model, pr, cache_dir) for it in items]
    missing = sum(s is None for s in sides)
    if missing:
        raise SystemExit(f"{model}: {missing} responses missing in {cache_dir}. No analysis until all items are cached.")
    return {"correct": np.array([s["correct"] for s in sides], dtype=bool),
            "valid": np.array([s["valid"] for s in sides], dtype=bool),
            "cost": np.array([s["cost"] for s in sides], dtype=float),
            "score": np.array([score({"small": s}, "margin") for s in sides], dtype=float),
            "snapshots": Counter(s["model_returned"] for s in sides),
            "finish": Counter(s["finish_reason"] for s in sides)}


def response_ids(items, cache_dir) -> set:
    ids = set()
    for m in H.MODELS:
        for it in items:
            with open(client.cache_path(cache_dir, m, it["id"]), encoding="utf-8") as f:
                ids.add(json.load(f)["response"]["id"])
    return ids


def operations(pre, heldout_items, shuffled_items, system, orig, shuf, spent, budget) -> dict:
    with open(RH.CALL_LOG, encoding="utf-8") as f:
        calls = [json.loads(l) for l in f if l.strip()]
    with open(RH.CACHE_LOG, encoding="utf-8") as f:
        cache = [json.loads(l) for l in f if l.strip()]
    ok = [c for c in calls if c["outcome"] == "ok"]
    failed = [c for c in calls if c["outcome"] != "ok"]

    mismatches = 0
    for run, items in (("heldout", heldout_items), ("perturbation", shuffled_items)):
        seen = {(c["model"], c["prompt_sha256"]) for c in ok if c["run"] == run}
        mismatches += sum((m, RH.prompt_hash(build_messages(it, system))) not in seen for m in H.MODELS for it in items)
    a, b = response_ids(heldout_items, CACHE_DIR), response_ids(shuffled_items, PERTURBATION_CACHE_DIR)
    final = RH.status_lines()
    other = [l for l in final if l[3:].strip('"') not in RH.RUN_OUTPUT | {"artifacts/heldout_results.json", "artifacts/heldout_report.md"}]
    changed = [p for p, h in pre["file_sha256"].items() if RH.sha256(ROOT / p) != h]
    return {"attempts": len(calls), "calls_ok": len(ok), "failed_attempts": len(failed),
            "errors": dict(Counter(f"{c['error']}:{c.get('status')}" for c in failed)) or "none",
            "calls_by_run": dict(Counter(f"{c['run']}/{c['model']}" for c in ok)),
            "cache_log": cache,
            "cache_summary": "; ".join(f"{c['run']}/{c['model']} (with {c['command_small']}) hits {c['hits']} misses {c['misses']} from {c['source']}" for c in cache),
            "prompt_hash_mismatches": mismatches, "response_ids_shared": len(a & b),
            "run_cost": {"heldout": sum(float(orig[m]["cost"].sum()) for m in H.MODELS),
                         "perturbation": sum(float(shuf[m]["cost"].sum()) for m in H.MODELS)},
            "ledger_delta": spent - pre["spent_before_usd"], "ledger_total": spent, "budget": budget,
            "decisions_unchanged": RH.sha256(ROOT / "docs/decisions.md") == pre["decisions_sha256"],
            "head_unchanged": RH.git("rev-parse", "HEAD") == pre["head"], "guarded_files_changed": changed,
            "unexpected_status": other, "final_status": final,
            "settings_unchanged": not changed and not other and RH.git("rev-parse", "HEAD") == pre["head"]}


def main():
    cfg, pr = experiment(), prices()
    pre = json.load(open(RH.PREFLIGHT, encoding="utf-8"))
    threshold = json.load(open(RH.FROZEN, encoding="utf-8"))["threshold"]
    if threshold != RH.THRESHOLD or threshold != pre["threshold_from_config"]:
        raise SystemExit("threshold differs from the preregistration")
    items, shuffled = read_jsonl(HELDOUT_FILE), read_jsonl(PERTURBATION_FILE)
    if [i["id"] for i in items] != [i["id"] for i in shuffled] or len(items) != RH.HELDOUT_N:
        raise SystemExit("the two runs are not paired by question ID")
    orig = {m: load_model(items, m, pr, CACHE_DIR) for m in H.MODELS}
    shuf = {m: load_model(shuffled, m, pr, PERTURBATION_CACHE_DIR) for m in H.MODELS}

    ledger = Ledger(LEDGER_FILE, cfg["budget"]["experiments_usd"])
    ops = operations(pre, items, shuffled, cfg["prompt"]["system"], orig, shuf, ledger.spent(), cfg["budget"]["experiments_usd"])
    problems = []
    if ops["prompt_hash_mismatches"]:
        problems.append(f"{ops['prompt_hash_mismatches']} responses do not match their prompt")
    if ops["response_ids_shared"]:
        problems.append(f"{ops['response_ids_shared']} responses are shared between the two caches")
    if not ops["settings_unchanged"]:
        problems.append(f"settings changed: {ops['guarded_files_changed']} {ops['unexpected_status']}")
    if problems:
        raise SystemExit("METHODOLOGICAL STOP: " + "; ".join(problems))

    levels = [it["level"] for it in items]
    r0, r1 = H.analyze_run(orig, levels, threshold), H.analyze_run(shuf, levels, threshold)
    flagged = np.array([s["position_dependent_option"] for s in shuffled], dtype=bool)
    cmp_ = H.compare_runs(orig, shuf, r0, r1, threshold, flagged)
    decision, why = H.decide(r0["primary"], bool(r0["non_dominance"]["dominated_by"]), cmp_["claims"]["both_hold"])
    res = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "preflight": {k: v for k, v in pre.items() if k != "file_sha256"},
           "original": r0, "perturbation": r1, "comparison": cmp_, "operations": ops, "decision": decision, "decision_reason": why,
           "perturbation_manifest": json.load(open(ARTIFACTS_DIR / "perturbation_manifest.json", encoding="utf-8")),
           "snapshots": {run: {m: dict(d[m]["snapshots"]) for m in H.MODELS} for run, d in (("original", orig), ("perturbation", shuf))},
           "finish_reasons": {run: {m: dict(d[m]["finish"]) for m in H.MODELS} for run, d in (("original", orig), ("perturbation", shuf))},
           "deviations": DEVIATIONS}
    res = H.finite(res)
    RESULTS.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT.write_text(H.report_md(res), encoding="utf-8")
    print(f"decision: {decision} | spent ${ops['ledger_total']:.4f}\n-> {RESULTS.name}, {REPORT.name}")


if __name__ == "__main__":
    main()
