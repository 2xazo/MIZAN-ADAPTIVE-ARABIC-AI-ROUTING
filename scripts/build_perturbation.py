"""No API, but it READS held-out: build the option-order perturbation set.

    python scripts/build_perturbation.py --i-have-go

Locked until the coordinator approves. Run only after the original held-out run has finished.
"""
import _common  # noqa: F401
import argparse
import json
import sys

from mizan.config import ARTIFACTS_DIR, HELDOUT_FILE, PERTURBATION_FILE
from mizan.data import read_jsonl, write_jsonl
from mizan.perturbation import perturb_items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--i-have-go", action="store_true", help="required: this reads held-out")
    args = ap.parse_args()
    if not args.i_have_go:
        sys.exit("Held-out is locked until the coordinator approves GO (--i-have-go).")
    items = read_jsonl(HELDOUT_FILE)
    shuffled, manifest = perturb_items(items)
    write_jsonl(PERTURBATION_FILE, shuffled)
    (ARTIFACTS_DIR / "perturbation_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(manifest)


if __name__ == "__main__":
    main()
