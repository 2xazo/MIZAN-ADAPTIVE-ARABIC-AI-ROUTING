"""Demo logic with no UI: one request routed at the frozen point, and the fixed example-selection rule.

The prompt, call settings, parsing and threshold are the frozen ones. Nothing here picks a threshold.
Live calls go to their own ledger, so the recorded experiment cost does not change.
"""
from __future__ import annotations

import http.client
import math

from . import client
from .config import ARTIFACTS_DIR
from .costs import BudgetError, Ledger, cost_usd, estimate_input_tokens, price_for
from .heldout import LARGE, SMALL
from .parsing import NOT_AVAILABLE, clean, parse_response
from .prompts import build_messages, valid_letters
from .routing import score

DEMO_LEDGER = ARTIFACTS_DIR / "demo_ledger.jsonl"
DEMO_TIMEOUT_S, DEMO_RETRIES = 20, 1  # a stage demo should fail fast; the frozen model settings are unaffected
HANDLED, ESCALATED = "handled", "escalated"
# Everything one live call can raise, so a failure stays a message on the page.
LIVE_ERRORS = (BudgetError, OSError, RuntimeError, ValueError, LookupError, TypeError, http.client.HTTPException)
# A presentation choice for the high-confidence example only. It has no effect on routing, on any
# evaluation item or on any result. See docs/decisions.md.
RELIGIOUS_SUBJECTS = ("Islamic Studies",)

SELECTION_RULE = {
    "high_confidence": "Among original held-out items accepted by Mizan and answered correctly by gpt-4o-mini, excluding "
                       "religious subjects (Islamic Studies), the highest finite margin. An item with no competing option "
                       "has no measured margin and is not eligible. Ties go to the lowest numeric item ID. The subject "
                       "exclusion is a presentation choice and has no effect on any result.",
    "lower_confidence": "Among original held-out items escalated by Mizan where gpt-4o-mini is wrong and gpt-4.1 is right, "
                        "the lowest finite margin. If no such item exists, the lowest finite margin among all escalated "
                        "items, with no claim of correction. Ties go to the lowest numeric item ID.",
}


def option_probabilities(token_logprobs: list[dict] | None, letters: str) -> list[dict]:
    """Probabilities of the valid letters at the answer token, highest first. These are exp(logprob)
    as returned, not renormalized. Same aggregation as `parse_response`."""
    if not token_logprobs:
        return []
    tok = next((t for t in token_logprobs if clean(t.get("token", ""))), None)
    if tok is None:
        return []
    probs: dict[str, float] = {}
    for alt in tok.get("top_logprobs") or []:
        c = clean(alt.get("token", ""))
        if c in letters and len(c) == 1:
            probs[c] = probs.get(c, 0.0) + math.exp(alt["logprob"])
    if clean(tok["token"]) in letters:
        probs.setdefault(clean(tok["token"]), math.exp(tok["logprob"]))
    return [{"letter": k, "probability": v} for k, v in sorted(probs.items(), key=lambda x: (-x[1], x[0]))]


def should_escalate(parsed: dict, threshold: float) -> bool:
    """Invalid output always escalates; `not_available` scores +inf and never does. Strictly below escalates."""
    return (not parsed["valid"]) or score({"small": parsed}, "margin") < threshold


def reason_line(parsed: dict, escalated: bool) -> str:
    if not parsed["valid"]:
        return "The economical model did not return one valid answer letter, so the request went to the stronger model."
    if escalated:
        return "The economical model's lead over the next option was too small to trust, so the request went to the stronger model."
    if parsed["margin"] == NOT_AVAILABLE:
        return "The economical model showed no competing option at all, so no stronger model was needed."
    return "The economical model's lead over the next option cleared the confidence threshold, so no stronger model was needed."


def _numeric_id(row: dict) -> tuple:
    return (0, int(row["id"])) if str(row["id"]).isdigit() else (1, str(row["id"]))


def select_examples(rows: list[dict], threshold: float) -> dict:
    """The fixed rule in SELECTION_RULE. `rows` have id, subject, margin (float or NOT_AVAILABLE), valid,
    small_correct and large_correct. Returns the two rows and whether a correction example exists."""
    finite = [r for r in rows if r["valid"] and r["margin"] != NOT_AVAILABLE]
    accepted = [r for r in finite if not r["margin"] < threshold and r["small_correct"] and r["subject"] not in RELIGIOUS_SUBJECTS]
    escalated = [r for r in finite if r["margin"] < threshold]
    corrected = [r for r in escalated if not r["small_correct"] and r["large_correct"]]
    if not accepted or not escalated:
        raise ValueError("the rule needs at least one accepted-and-correct item and one escalated item")
    high = min(accepted, key=lambda r: (-r["margin"], _numeric_id(r)))
    low = min(corrected or escalated, key=lambda r: (r["margin"], _numeric_id(r)))
    return {"high_confidence": high, "lower_confidence": low, "correction_available": bool(corrected)}


def stronger_corrected(small_letter: str | None, large_letter: str | None, correct: str | None) -> bool:
    """True only with a known answer key, an actual escalation, a wrong first answer and a right second one."""
    return bool(correct and large_letter and small_letter != correct and large_letter == correct)


def has_live_key() -> bool:
    import os
    return bool(os.environ.get("OPENAI_API_KEY", "").strip()) and not os.environ.get("MIZAN_DISABLE_LIVE")


def failure_message(err: Exception) -> str:
    """Fixed text for the page. The exception's own text is never used, because an API error can quote part of the key."""
    if isinstance(err, BudgetError):
        return "The live spending limit stopped this call."
    if isinstance(err, client.ApiError):
        if err.status in (401, 403):
            return "The API did not accept the configured credentials."
        if err.status == 429:
            return "The API is limiting requests right now. Try again shortly."
        return "The API is having problems right now." if err.status >= 500 else f"The API rejected the request (HTTP {err.status})."
    if isinstance(err, OSError):  # includes timeouts and connection errors
        return "The model did not answer in time or could not be reached."
    return "The model returned an unexpected response."


def _call(item: dict, model: str, system: str, call_cfg: dict, prices: dict, ledger: Ledger) -> tuple[dict, dict]:
    messages = build_messages(item, system)
    price = price_for(prices, model)
    ledger.check(cost_usd(estimate_input_tokens(messages), call_cfg["max_output_tokens"] + 64, price))
    resp, latency = client.chat(client.build_payload(model, messages, call_cfg), DEMO_TIMEOUT_S, DEMO_RETRIES)
    ex = client.extract(resp)
    cost = cost_usd(ex["input_tokens"], ex["output_tokens"], price)
    ledger.record(model, "demo", ex["input_tokens"], ex["output_tokens"], cost)
    parsed = parse_response(ex["content"], ex["token_logprobs"], valid_letters(item))
    return parsed, {"input_tokens": ex["input_tokens"], "output_tokens": ex["output_tokens"], "cost_usd": cost,
                    "model_returned": ex["model_returned"], "latency_s": latency,
                    "option_probabilities": option_probabilities(ex["token_logprobs"], valid_letters(item))}


def live_request(item: dict, cfg: dict, prices: dict, threshold: float) -> dict:
    """One real request through the frozen route. Costs money. Same shape as `recorded_request`."""
    ledger = Ledger(DEMO_LEDGER, cfg["budget"]["reserve_usd"])
    small, small_meta = _call(item, SMALL, cfg["prompt"]["system"], cfg["call"], prices, ledger)
    escalated = should_escalate(small, threshold)
    large, large_meta, large_error = None, None, None
    if escalated:
        try:
            large, large_meta = _call(item, LARGE, cfg["prompt"]["system"], cfg["call"], prices, ledger)
        except LIVE_ERRORS as err:  # the first call is already paid for and shown; there is simply no final answer
            large_error = failure_message(err)
    # With no gpt-4.1 response for this request, its cost is the same tokens at gpt-4.1 prices.
    always = large_meta["cost_usd"] if large_meta else cost_usd(small_meta["input_tokens"], small_meta["output_tokens"], price_for(prices, LARGE))
    return {"source": "live", "decision": ESCALATED if escalated else HANDLED, "reason": reason_line(small, escalated),
            "threshold": threshold, "margin": small["margin"], "small_valid": small["valid"], "small_answer": small["letter"],
            "large_answer": large["letter"] if large else None, "large_valid": large["valid"] if large else None, "large_error": large_error,
            "final_answer": (large["letter"] if large else None) if escalated else small["letter"],
            "cost_usd": small_meta["cost_usd"] + (large_meta["cost_usd"] if large_meta else 0.0), "always_large_cost_usd": always,
            "always_large_cost_kind": "measured" if large_meta else "estimated", "prices_verified_on": prices.get("verified_on"),
            "small": small_meta, "large": large_meta,
            "corrected": stronger_corrected(small["letter"], large["letter"] if large else None, item.get("answer"))}


def recorded_request(example: dict) -> dict:
    """The saved run of one entry from demo_examples.json, in the same shape as `live_request`."""
    escalated = example["decision"] == ESCALATED
    return {"source": "recorded", "decision": example["decision"], "reason": example["reason"], "threshold": example["threshold"],
            "margin": example["margin"], "small_answer": example["gpt_4o_mini"]["answer"],
            "large_answer": example["gpt_4_1"]["answer"] if escalated else None, "large_valid": True if escalated else None,
            "final_answer": example["final_answer"], "cost_usd": example["cost_of_request_usd"],
            "always_large_cost_usd": example["cost_always_gpt_4_1_usd"], "always_large_cost_kind": "measured",
            "small": example["gpt_4o_mini"], "large": example["gpt_4_1"] if escalated else None,
            "corrected": example["stronger_model_corrected"]}
