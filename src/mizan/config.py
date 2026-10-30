"""Paths and config loading. Single place that knows where things live."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
ARTIFACTS_DIR = ROOT / "artifacts"

DEV_FILE = PROCESSED_DIR / "dev.jsonl"
HELDOUT_FILE = PROCESSED_DIR / "heldout.jsonl"
PERTURBATION_FILE = PROCESSED_DIR / "heldout_option_order.jsonl"
PERTURBATION_CACHE_DIR = DATA_DIR / "cache_option_order"  # same ids as held-out, so never share its cache
SPLIT_IDS_FILE = ARTIFACTS_DIR / "split_ids.json"   # IDs only: safe to commit
LEDGER_FILE = ARTIFACTS_DIR / "cost_ledger.jsonl"
PROBE_FILE = ARTIFACTS_DIR / "model_probe.json"
RESULTS_FILE = ARTIFACTS_DIR / "results.json"        # the single source of truth
REPORT_FILE = ARTIFACTS_DIR / "gonogo_report.md"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def experiment() -> dict:
    return load_yaml("experiment.yaml")


def prices() -> dict:
    pr = load_yaml("prices.yaml")
    # YAML parses an unquoted YYYY-MM-DD as a date, which results.json cannot serialize.
    if pr.get("verified_on") is not None:
        pr["verified_on"] = str(pr["verified_on"])
    return pr
