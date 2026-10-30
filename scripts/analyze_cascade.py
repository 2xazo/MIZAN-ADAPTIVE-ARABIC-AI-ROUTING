"""OFFLINE, no API: Dev 300 confirmation of singles, pairs and the three-step cascade.

    python scripts/analyze_cascade.py

Reads Dev items and cached responses only. Adds the `dev300` section to artifacts/results.json
(other sections are kept) and writes artifacts/dev300_report.md.
"""
import _common  # noqa: F401
import json
import math
import time

import numpy as np

from mizan import dev300
from mizan.config import ARTIFACTS_DIR, DEV_FILE, LEDGER_FILE, RESULTS_FILE, experiment, prices
from mizan.costs import Ledger
from mizan.data import read_jsonl
from mizan.routing import SIGNALS, score
from mizan.runner import load_side

REPORT = ARTIFACTS_DIR / "dev300_report.md"


def load_model(items, model, pr):
    sides = [load_side(it, model, pr) for it in items]
    missing = sum(s is None for s in sides)
    if missing:
        raise SystemExit(f"{model}: {missing} items are not cached. Run scripts/run_eval.py --n 300 first.")
    return {
        "correct": np.array([s["correct"] for s in sides], dtype=bool),
        "valid": np.array([s["valid"] for s in sides], dtype=bool),
        "cost": np.array([s["cost"] for s in sides], dtype=float),
        "confidence": np.array([math.exp(s["raw_logprob"]) if s["valid"] else 0.0 for s in sides]),
        "normalized_complete": np.array([s["normalized_complete"] for s in sides], dtype=bool),
        "margin_missing": np.array([s["margin"] == "not_available" for s in sides], dtype=bool),
        "scores": {sig: np.array([score({"small": s}, sig) for s in sides]) for sig in SIGNALS},
        "latency_s_raw": [s["latency"] for s in sides],
    }


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


def main():
    cfg, pr = experiment(), prices()
    items = read_jsonl(DEV_FILE)[:300]
    if len(items) != 300:
        raise SystemExit(f"expected 300 Dev items, found {len(items)}")
    models = (dev300.CHEAP, dev300.MID, dev300.TOP)
    full = {m: load_model(items, m, pr) for m in models}

    res = dev300.stamp(dev300.analyze_dev(full, [it["id"] for it in items], seed=cfg["seed"]))
    res["latency_s_raw"] = {m: full[m]["latency_s_raw"] for m in models}
    res["prices"] = {"verified_on": pr["verified_on"], "source_url": pr["source_url"],
                     "models": {m: pr["models"][m] for m in models}}
    res["prompt_system"] = cfg["prompt"]["system"]
    ledger = Ledger(LEDGER_FILE, cfg["budget"]["experiments_usd"])
    res["spent_usd"] = ledger.spent()
    res["budget_experiments_usd"] = cfg["budget"]["experiments_usd"]

    results = {}
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, encoding="utf-8") as f:
            results = json.load(f)
    results["dev300"] = finite(res)
    results["dev300_generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = RESULTS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    tmp.replace(RESULTS_FILE)

    REPORT.write_text(dev300.report_md(results["dev300"], res["spent_usd"], res["budget_experiments_usd"]), encoding="utf-8")
    print(f"decision: {res['decision']} | chosen: {res['chosen_design']} | spent ${res['spent_usd']:.4f}")
    print(f"-> {RESULTS_FILE.name}, {REPORT.name}")


if __name__ == "__main__":
    main()
