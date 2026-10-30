"""Paid and gated: the approved held-out run, one step at a time.

    python scripts/run_heldout.py preflight       # no API; records the final check, stops on any failure
    python scripts/run_heldout.py original        # section 12 step 1, through scripts/run_eval.py
    python scripts/run_heldout.py perturbation    # section 12 steps 3 and 4

Existing code is not changed. `client._request` is wrapped only to log each attempt, its prompt hash
and its source run. Items already cached are never re-sent.
"""
import _common  # noqa: F401
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import build_perturbation
import run_eval
from mizan import client
from mizan.config import (ARTIFACTS_DIR, CACHE_DIR, DEV_FILE, HELDOUT_FILE, LEDGER_FILE, PERTURBATION_CACHE_DIR,
                          PERTURBATION_FILE, PROBE_FILE, ROOT, SPLIT_IDS_FILE, experiment, prices)
from mizan.costs import Ledger, cost_usd, estimate_input_tokens, price_for, require_verified
from mizan.data import read_jsonl
from mizan.heldout import LARGE, MID, MODELS, SMALL
from mizan.prompts import build_messages

APPROVED_COMMIT = "a34020c1e01758f9098cf529c5e7b615088805ba"
THRESHOLD = 6.249999994711611
TARGET_RATE = 0.3
HELDOUT_N = 500
SYSTEM = ("You answer Arabic multiple-choice questions. Return exactly one uppercase ASCII letter from the "
          "available choices. Return no explanation.")
PRICES = {SMALL: {"input": 0.15, "output": 0.60}, MID: {"input": 0.40, "output": 1.60}, LARGE: {"input": 2.00, "output": 8.00}}
CALL = {"temperature": 0, "logprobs": True, "top_logprobs": 20, "max_output_tokens": 3}
DEV_SNAPSHOTS = {SMALL: "gpt-4o-mini-2024-07-18", MID: "gpt-4.1-mini-2025-04-14", LARGE: "gpt-4.1-2025-04-14"}
PREFLIGHT = ARTIFACTS_DIR / "heldout_preflight.json"
CALL_LOG = ARTIFACTS_DIR / "heldout_call_log.jsonl"
CACHE_LOG = ARTIFACTS_DIR / "heldout_cache_log.jsonl"
FROZEN = ARTIFACTS_DIR / "frozen_operating_point.json"
# Only these may change during the run; they hold run output, not settings.
RUN_OUTPUT = {"artifacts/cost_ledger.jsonl", "artifacts/heldout_preflight.json", "artifacts/heldout_call_log.jsonl",
              "artifacts/heldout_cache_log.jsonl", "artifacts/perturbation_manifest.json"}
SPLITS = {"heldout": (HELDOUT_FILE, CACHE_DIR), "perturbation": (PERTURBATION_FILE, PERTURBATION_CACHE_DIR)}
GUARDED = ("config/experiment.yaml", "config/prices.yaml", "artifacts/frozen_operating_point.json", "artifacts/model_probe.json",
           "docs/decisions.md", "src/mizan/client.py", "src/mizan/parsing.py", "src/mizan/prompts.py", "src/mizan/routing.py",
           "src/mizan/cascade.py", "src/mizan/curve.py", "src/mizan/heldout.py", "src/mizan/metrics.py", "src/mizan/perturbation.py",
           "src/mizan/runner.py", "src/mizan/costs.py", "scripts/run_eval.py", "scripts/run_heldout.py",
           "scripts/build_perturbation.py", "scripts/analyze_heldout.py", "data/processed/heldout.jsonl")


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def sha256(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def prompt_hash(messages: list[dict]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def status_lines() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l.strip()]


def stop(why: str):
    sys.exit(f"STOP, held-out not run: {why}")


def preflight() -> None:
    if PREFLIGHT.exists():
        stop(f"{PREFLIGHT.name} already exists; the final check runs once.")
    lines = status_lines()
    if lines:
        stop(f"git status is not clean: {lines}")
    head = git("rev-parse", "HEAD")
    added = git("diff", "--name-status", APPROVED_COMMIT, head).splitlines()
    if any(not l.startswith("A") for l in added):
        stop(f"commits after the approved one do more than add files: {added}")

    cfg, pr, frozen = experiment(), prices(), json.load(open(FROZEN, encoding="utf-8"))
    require_verified(pr)
    if (frozen["threshold"], frozen["target_rate"], frozen["signal"], frozen["small"], frozen["large"]) != (THRESHOLD, TARGET_RATE, "margin", SMALL, LARGE):
        stop("frozen operating point differs from the preregistration")
    if cfg["prompt"]["system"] != SYSTEM:
        stop("system prompt differs from the preregistration")
    if {k: cfg["call"][k] for k in CALL} != CALL:
        stop("call parameters differ from the preregistration")
    if {m: pr["models"][m] for m in MODELS} != PRICES or str(pr["verified_on"]) != "2026-10-30":
        stop("prices differ from the preregistration")
    if cfg["budget"]["experiments_usd"] != 8.0:
        stop("experiment budget is not $8")
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        stop("OPENAI_API_KEY is not set")
    probe = json.load(open(PROBE_FILE, encoding="utf-8"))["models"]
    if any(probe[m]["overrides"] for m in MODELS):
        stop("a probe override would change the call parameters")

    items, dev = read_jsonl(HELDOUT_FILE), read_jsonl(DEV_FILE)
    ids, dev_ids = [it["id"] for it in items], {it["id"] for it in dev}
    split = json.load(open(SPLIT_IDS_FILE, encoding="utf-8"))
    if len(items) != HELDOUT_N or len(set(ids)) != HELDOUT_N or set(ids) != set(split["heldout_ids"]):
        stop("held-out items do not match the recorded 500 IDs")
    if set(ids) & dev_ids:
        stop("held-out and Dev share IDs")
    if PERTURBATION_FILE.exists() or PERTURBATION_CACHE_DIR.exists():
        stop("the option-order set or its cache already exists")
    if CACHE_DIR.resolve() == PERTURBATION_CACHE_DIR.resolve():
        stop("the two caches are the same directory")
    cached = {m: sum(client.cache_path(CACHE_DIR, m, i).exists() for i in ids) for m in MODELS}
    if any(cached.values()):
        stop(f"held-out responses are already cached: {cached}")
    dev_text = {(it.get("context"), it["question"]) for it in dev}
    overlap = sum((it.get("context"), it["question"]) in dev_text for it in items)

    worst = {m: sum(cost_usd(estimate_input_tokens(build_messages(it, cfg["prompt"]["system"])), cfg["call"]["max_output_tokens"] + 64,
                             price_for(pr, m)) for it in items) for m in MODELS}
    spent = Ledger(LEDGER_FILE, cfg["budget"]["experiments_usd"]).spent()
    max_cost = 2 * sum(worst.values())
    if spent + max_cost > cfg["budget"]["experiments_usd"]:
        stop(f"maximum cost ${max_cost:.4f} + spent ${spent:.4f} exceeds the budget")

    record = {"recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "approved_commit": APPROVED_COMMIT, "head": head,
              "git_status_porcelain": lines, "added_since_approved": [l.split("\t", 1)[1] for l in added],
              "decisions_sha256": sha256(ROOT / "docs/decisions.md"), "threshold_from_config": frozen["threshold"],
              "target_rate": frozen["target_rate"], "signal": frozen["signal"],
              "model_aliases_sent": list(MODELS), "dev_snapshots_expected": DEV_SNAPSHOTS,
              "prices_per_1m": {m: pr["models"][m] for m in MODELS}, "prices_verified_on": str(pr["verified_on"]),
              "heldout_size": len(items), "heldout_dev_id_overlap": 0, "heldout_dev_same_question_text": overlap,
              "caches": {"original": str(CACHE_DIR.relative_to(ROOT)), "option_order": str(PERTURBATION_CACHE_DIR.relative_to(ROOT))},
              "max_expected_cost_usd": max_cost, "max_cost_per_model_per_run_usd": worst, "spent_before_usd": spent,
              "budget_usd": cfg["budget"]["experiments_usd"], "file_sha256": {p: sha256(ROOT / p) for p in GUARDED}}
    PREFLIGHT.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "file_sha256"}, ensure_ascii=False, indent=1))


def guard() -> dict:
    """Runs before each paid step. Any change to settings or code stops the run."""
    if not PREFLIGHT.exists():
        stop("run preflight first")
    pre = json.load(open(PREFLIGHT, encoding="utf-8"))
    if git("rev-parse", "HEAD") != pre["head"]:
        stop("HEAD moved after the final check")
    other = [l for l in status_lines() if l[3:].strip('"') not in RUN_OUTPUT]
    if other:
        stop(f"unexpected tracked or new files: {other}")
    changed = [p for p, h in pre["file_sha256"].items() if sha256(ROOT / p) != h]
    if changed:
        stop(f"guarded files changed: {changed}")
    return pre


def _append(path, row: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _log_calls(run: str, items: list[dict], system: str) -> None:
    by_hash = {}
    for it in items:
        by_hash.setdefault(prompt_hash(build_messages(it, system)), []).append(it["id"])
    original = client._request

    def logged(method, path, payload, timeout):
        if path != "/chat/completions":
            return original(method, path, payload, timeout)
        h = prompt_hash(payload["messages"])
        row = {"ts": time.time(), "run": run, "model": payload["model"], "item_ids": by_hash.get(h, []), "prompt_sha256": h}
        try:
            resp = original(method, path, payload, timeout)
        except Exception as e:
            _append(CALL_LOG, {**row, "outcome": "error", "error": type(e).__name__, "status": getattr(e, "status", None)})
            raise
        _append(CALL_LOG, {**row, "outcome": "ok", "response_id": resp.get("id"), "model_returned": resp.get("model")})
        return resp

    client._request = logged


def _logged_ok(run: str) -> set:
    if not CALL_LOG.exists():
        return set()
    with open(CALL_LOG, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return {(r["model"], r["prompt_sha256"]) for r in rows if r["run"] == run and r["outcome"] == "ok"}


def run_split(split: str) -> None:
    items_file, cache_dir = SPLITS[split]
    cfg = experiment()
    items = read_jsonl(items_file)
    if len(items) != HELDOUT_N:
        stop(f"{split} has {len(items)} items, expected {HELDOUT_N}")
    # Anything already in this cache must be this run's own earlier call for this exact prompt.
    ok = _logged_ok(split)
    for m in MODELS:
        for it in items:
            if client.cache_path(cache_dir, m, it["id"]).exists() and (m, prompt_hash(build_messages(it, cfg["prompt"]["system"]))) not in ok:
                stop(f"{m}/{it['id']} is cached in {cache_dir} with no matching call from run {split}")
    _log_calls(split, items, cfg["prompt"]["system"])
    for small in (SMALL, MID):
        guard()
        hits = {m: sum(client.cache_path(cache_dir, m, it["id"]).exists() for it in items) for m in (small, LARGE)}
        sys.argv = ["run_eval.py", "--small", small, "--large", LARGE, "--split", split, "--n", str(HELDOUT_N), "--i-have-go"]
        run_eval.main()
        for m, h in hits.items():
            _append(CACHE_LOG, {"ts": time.time(), "run": split, "command_small": small, "model": m, "source": str(cache_dir.relative_to(ROOT)),
                                "hits": h, "misses": HELDOUT_N - h})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["preflight", "original", "perturbation"])
    args = ap.parse_args()
    if args.step == "preflight":
        preflight()
    elif args.step == "original":
        guard()
        run_split("heldout")
    else:
        guard()
        items = read_jsonl(HELDOUT_FILE)
        missing = sum(not client.cache_path(CACHE_DIR, m, it["id"]).exists() for m in MODELS for it in items)
        if missing:
            stop(f"the original run is incomplete: {missing} responses missing")
        if not PERTURBATION_FILE.exists():
            sys.argv = ["build_perturbation.py", "--i-have-go"]
            build_perturbation.main()
        run_split("perturbation")


if __name__ == "__main__":
    main()
