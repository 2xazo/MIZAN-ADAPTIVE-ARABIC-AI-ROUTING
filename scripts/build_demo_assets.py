"""OFFLINE, no API: builds the app's assets from the local held-out caches. Changes no result.

    python scripts/build_demo_assets.py

Writes artifacts/heldout_per_item.json (per-item outcomes, IDs only, no question text) and
artifacts/demo_examples.json (two real examples with question text and English translations,
which come from artifacts/demo_translations.json).
"""
import _common  # noqa: F401
import json
import math
import sys

from mizan import demo as D, heldout as H
from mizan.config import ARTIFACTS_DIR, CACHE_DIR, HELDOUT_FILE, PERTURBATION_CACHE_DIR, PERTURBATION_FILE, prices
from mizan.data import read_jsonl
from mizan.runner import load_side
from mizan.client import cache_path, extract
from mizan.prompts import valid_letters
from mizan.routing import score

PER_ITEM = ARTIFACTS_DIR / "heldout_per_item.json"
EXAMPLES = ARTIFACTS_DIR / "demo_examples.json"
TRANSLATIONS = ARTIFACTS_DIR / "demo_translations.json"
LICENSE_NOTE = ("Question text from ArabicMMLU (Koto et al., Findings of ACL 2024, MBZUAI), licensed CC BY-NC-SA 4.0 per its GitHub "
                "repository and CC BY-NC 4.0 per its Hugging Face card. Non-commercial use only. English translations are "
                "adaptations made for this demo and are shared under CC BY-NC-SA 4.0.")


def columns(items, pr, cache_dir):
    out = {}
    for m in H.MODELS:
        sides = [load_side(it, m, pr, cache_dir) for it in items]
        if any(s is None for s in sides):
            raise SystemExit(f"{m}: responses missing in {cache_dir}")
        scores = [score({"small": s}, "margin") for s in sides]
        out[m] = {"correct": [s["correct"] for s in sides], "valid": [s["valid"] for s in sides],
                  "cost_usd": [s["cost"] for s in sides], "answer": [s["letter"] for s in sides]}
        if m == H.SMALL:
            out[m]["margin"] = [s if math.isfinite(s) else ("inf" if s > 0 else "-inf") for s in scores]
    return out


def side_summary(item, model, pr):
    side = load_side(item, model, pr, CACHE_DIR)
    with open(cache_path(CACHE_DIR, model, item["id"]), encoding="utf-8") as f:
        ex = extract(json.load(f)["response"])
    return side, {"answer": side["letter"], "option_probabilities": D.option_probabilities(ex["token_logprobs"], valid_letters(item)),
                  "input_tokens": side["input_tokens"], "output_tokens": side["output_tokens"], "cost_usd": side["cost"],
                  "model_returned": side["model_returned"]}


def example(item, role, pr, threshold, translations):
    small, small_out = side_summary(item, H.SMALL, pr)
    large, large_out = side_summary(item, H.LARGE, pr)
    escalated = D.should_escalate(small, threshold)
    tr = translations.get(item["id"])
    if tr is None:
        print(f"translation missing for {role} item {item['id']}:\n{json.dumps(item, ensure_ascii=False, indent=1)}")
    return {"role": role, "label": "Example from the held-out set", "selection_rule": D.SELECTION_RULE[role], "id": item["id"],
            "subject": item["subject"], "level": item["level"], "context": item["context"], "question": item["question"],
            "options": item["options"], "correct_answer": item["answer"], "english": tr,
            "gpt_4o_mini": small_out, "margin": small["margin"], "threshold": threshold,
            "decision": D.ESCALATED if escalated else D.HANDLED, "reason": D.reason_line(small, escalated),
            "gpt_4_1": large_out if escalated else None, "final_answer": large["letter"] if escalated else small["letter"],
            "answered_correctly": bool(large["correct"] if escalated else small["correct"]),
            "stronger_model_corrected": escalated and D.stronger_corrected(small["letter"], large["letter"], item["answer"]),
            "cost_of_request_usd": small["cost"] + (large["cost"] if escalated else 0.0), "cost_always_gpt_4_1_usd": large["cost"],
            "license": LICENSE_NOTE}


def main():
    pr = prices()
    results = json.load(open(ARTIFACTS_DIR / "heldout_results.json", encoding="utf-8"))
    threshold = results["original"]["threshold"]
    items, shuffled = read_jsonl(HELDOUT_FILE), read_jsonl(PERTURBATION_FILE)
    orig, shuf = columns(items, pr, CACHE_DIR), columns(shuffled, pr, PERTURBATION_CACHE_DIR)
    PER_ITEM.write_text(json.dumps({"note": "Per-item outcomes of the recorded held-out runs. IDs only, no question text.",
                                    "threshold": threshold, "ids": [i["id"] for i in items], "levels": [i["level"] for i in items],
                                    "position_dependent": [s["position_dependent_option"] for s in shuffled],
                                    "original": orig, "perturbation": shuf}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    rows = []
    for k, it in enumerate(items):
        margin = orig[H.SMALL]["margin"][k]
        rows.append({"id": it["id"], "subject": it["subject"], "valid": orig[H.SMALL]["valid"][k], "small_correct": orig[H.SMALL]["correct"][k],
                     "large_correct": orig[H.LARGE]["correct"][k], "margin": "not_available" if margin == "inf" else margin})
    chosen = D.select_examples(rows, threshold)
    by_id = {i["id"]: i for i in items}
    translations = json.load(open(TRANSLATIONS, encoding="utf-8")) if TRANSLATIONS.exists() else {}
    out = {"selection_rule": D.SELECTION_RULE, "correction_example_available": chosen["correction_available"],
           "examples": {role: example(by_id[chosen[role]["id"]], role, pr, threshold, translations) for role in ("high_confidence", "lower_confidence")}}
    if any(e["english"] is None for e in out["examples"].values()):
        sys.exit("Add the translations above to artifacts/demo_translations.json, then run again. demo_examples.json was not written.")
    EXAMPLES.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {PER_ITEM.name}, {EXAMPLES.name}")


if __name__ == "__main__":
    main()
