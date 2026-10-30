"""Download ArabicMMLU, normalize options to A-E, and build a fixed stratified Dev/Held-out split.

    python scripts/prepare_data.py                 # from Hugging Face (needs `datasets`)
    python scripts/prepare_data.py --csv FILE.csv  # from a local export of the dataset

Writes data/processed/{dev,heldout}.jsonl (git-ignored: contain question text) and
artifacts/split_ids.json (IDs + rejection log only: safe to commit).
"""
import _common  # noqa: F401
import argparse
import csv
import json
from collections import Counter

from mizan.config import DEV_FILE, HELDOUT_FILE, SPLIT_IDS_FILE, experiment
from mizan.data import normalize_row, stratified_split, write_jsonl


def load_rows(args, cfg):
    if args.csv:
        with open(args.csv, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    from datasets import load_dataset
    ds = load_dataset(cfg["data"]["dataset"], cfg["data"]["hf_config"], split=cfg["data"]["hf_split"])
    return [dict(r) for r in ds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    args = ap.parse_args()
    cfg = experiment()

    rows = load_rows(args, cfg)
    print(f"raw rows: {len(rows)}; columns: {sorted(rows[0].keys())}")
    items, rejects = [], Counter()
    seen = set()
    for r in rows:
        it, why = normalize_row(r)
        if it is None:
            rejects[why] += 1
        elif it["id"] in seen:
            rejects["duplicate_id"] += 1
        else:
            seen.add(it["id"])
            items.append(it)
    print(f"valid items: {len(items)}; rejected: {dict(rejects)}")

    keys = [k.lower() for k in cfg["data"]["stratify_by"]]
    dev, held = stratified_split(items, cfg["data"]["dev_size"], cfg["data"]["heldout_size"],
                                 cfg["seed"], keys)
    write_jsonl(DEV_FILE, dev)
    write_jsonl(HELDOUT_FILE, held)
    SPLIT_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SPLIT_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump({"dataset": cfg["data"]["dataset"], "seed": cfg["seed"],
                   "stratify_by": cfg["data"]["stratify_by"], "total_raw": len(rows),
                   "total_valid": len(items), "rejected": dict(rejects),
                   "options_count": dict(Counter(len(i["options"]) for i in items)),
                   "dev_ids": [d["id"] for d in dev], "heldout_ids": [h["id"] for h in held]},
                  f, ensure_ascii=False, indent=1)
    print(f"dev={len(dev)} heldout={len(held)} -> {DEV_FILE.name}, {HELDOUT_FILE.name}, {SPLIT_IDS_FILE.name}")


if __name__ == "__main__":
    main()
