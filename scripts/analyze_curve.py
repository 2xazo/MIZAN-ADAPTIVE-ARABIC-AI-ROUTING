"""OFFLINE, no API: Dev 300 escalation table for gpt-4o-mini -> gpt-4.1, and the frozen point.

    python scripts/analyze_curve.py

Reads Dev items and cached responses only. Writes artifacts/dev300_curve.md and
artifacts/frozen_operating_point.json. Refuses to overwrite a frozen point with a different one.
"""
import _common  # noqa: F401
import json
import time

from analyze_cascade import finite, load_model
from mizan import curve, dev300
from mizan.config import ARTIFACTS_DIR, DEV_FILE, experiment, prices
from mizan.data import read_jsonl

SIGNAL = "margin"
REPORT = ARTIFACTS_DIR / "dev300_curve.md"
FROZEN = ARTIFACTS_DIR / "frozen_operating_point.json"


def main():
    cfg, pr = experiment(), prices()
    items = read_jsonl(DEV_FILE)[:300]
    if len(items) != 300:
        raise SystemExit(f"expected 300 Dev items, found {len(items)}")
    names = (dev300.CHEAP, dev300.MID, dev300.TOP)
    full = {m: load_model(items, m, pr) for m in names}
    small, large = (dict(full[m], score=full[m]["scores"][SIGNAL]) for m in (dev300.CHEAP, dev300.TOP))
    baselines = {m: curve.always(full[m]) for m in names}

    rows = curve.table(small, large, baselines, seed=cfg["seed"])
    chosen = curve.choose_rule(rows, baselines[dev300.TOP]["accuracy"])
    pair = dev300.name_of([dev300.CHEAP, dev300.TOP])
    REPORT.write_text(curve.report_md(rows, chosen, baselines, pair, SIGNAL, dev300.TOP, len(items), 1000), encoding="utf-8")

    frozen = None if chosen is None else {
        "decision": "GO to preregistration", "pair": pair, "small": dev300.CHEAP, "large": dev300.TOP, "signal": SIGNAL,
        "rule": "The LOWEST escalation rate whose Dev 300 accuracy is >= Always gpt-4.1 accuracy minus 4 percentage points.",
        "target_rate": chosen["target_rate"], "threshold": chosen["threshold"],
        "dev300": {k: chosen[k] for k in ("escalated_items", "achieved_rate", "accuracy", "total_cost_usd", "saving_vs_top",
                                          "mizan_minus_random", "accepted_accuracy", "error_in_escalated", "dominated_by")},
        "dev300_always": baselines, "prices": {"verified_on": pr["verified_on"], "models": {m: pr["models"][m] for m in names}},
        "seed": cfg["seed"], "recalibrated_on_heldout": False}
    if FROZEN.exists():
        with open(FROZEN, encoding="utf-8") as f:
            old = json.load(f)
        if frozen is None or (old["target_rate"], old["threshold"]) != (frozen["target_rate"], frozen["threshold"]):
            raise SystemExit("A different operating point is already frozen. It is never replaced.")
    elif frozen:
        frozen["frozen_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        FROZEN.write_text(json.dumps(finite(frozen), ensure_ascii=False, indent=1), encoding="utf-8")
    print("NO-GO: no grid point satisfies the rule" if chosen is None else
          f"operating point: target {chosen['target_rate']:.2f}, threshold {chosen['threshold']}, "
          f"accuracy {chosen['accuracy']:.4f}")
    print(f"-> {REPORT.name}")


if __name__ == "__main__":
    main()
