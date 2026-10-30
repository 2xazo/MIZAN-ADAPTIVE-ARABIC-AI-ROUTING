"""Paid step: run small + large models on DEV (or held-out after GO) with caching and budget stop.

    python scripts/run_eval.py --small gpt-4.1-mini --large gpt-4.1 --split dev --n 5     # smoke
    python scripts/run_eval.py --small gpt-4.1-mini --large gpt-4.1 --split dev --n 100   # Go/No-Go

Already-cached items are never re-called. Held-out requires --i-have-go.
"""
import _common  # noqa: F401
import argparse
import json
import sys

from mizan.config import DEV_FILE, HELDOUT_FILE, LEDGER_FILE, PROBE_FILE, experiment, prices
from mizan.costs import BudgetError, Ledger, require_verified
from mizan.data import read_jsonl
from mizan.runner import run_model


def overrides_for(model):
    """Reuse the param set the live probe found working for this model."""
    if not PROBE_FILE.exists():
        sys.exit("Run scripts/probe_models.py first.")
    with open(PROBE_FILE, encoding="utf-8") as f:
        entry = json.load(f)["models"].get(model)
    if not entry or not entry.get("ok"):
        sys.exit(f"{model} did not pass the probe; pick another candidate.")
    if model and not entry.get("logprobs_returned"):
        print(f"WARNING: {model} returned no logprobs (fine for the large model only).")
    ov = dict(entry["overrides"])
    for k in ("max_completion_tokens",):  # keep the configured output limit
        if k in ov:
            ov[k] = experiment()["call"]["max_output_tokens"]
    return ov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", required=True)
    ap.add_argument("--large", required=True)
    ap.add_argument("--split", choices=["dev", "heldout"], default="dev")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--i-have-go", action="store_true", help="required for held-out")
    args = ap.parse_args()

    if args.split == "heldout" and not args.i_have_go:
        sys.exit("Held-out is locked until the coordinator approves GO (--i-have-go).")
    cfg, pr = experiment(), prices()
    require_verified(pr)
    items = read_jsonl(DEV_FILE if args.split == "dev" else HELDOUT_FILE)[: args.n]
    ledger = Ledger(LEDGER_FILE, cfg["budget"]["experiments_usd"])
    try:
        for m in (args.small, args.large):
            run_model(items, m, cfg["call"], cfg["prompt"]["system"], pr, ledger, overrides_for(m))
    except BudgetError as e:
        sys.exit(f"BUDGET STOP: {e}")
    print(f"done. total spent: ${ledger.spent():.4f} / ${cfg['budget']['experiments_usd']:.2f}")


if __name__ == "__main__":
    main()
