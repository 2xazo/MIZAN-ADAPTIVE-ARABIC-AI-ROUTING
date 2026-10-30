"""OFFLINE, no API, no key, no question text: recomputes the reported results and compares them.

    python scripts/recompute_offline.py

Reads artifacts/heldout_per_item.json, runs the same analysis code as the evaluation, and checks every
number under `original`, `perturbation` and `comparison` in artifacts/heldout_results.json. Writes
nothing. Exits non-zero on any difference.
"""
import _common  # noqa: F401
import sys

from mizan.story import recompute_differences


def main():
    diffs, checked = recompute_differences()
    if diffs:
        for path, got, want in diffs[:50]:
            print(f"DIFFERENT {path}: recomputed {got}, recorded {want}")
        sys.exit(f"{len(diffs)} of {checked} values differ")
    print(f"{checked} values recomputed from per-item outcomes; all match artifacts/heldout_results.json")


if __name__ == "__main__":
    main()
