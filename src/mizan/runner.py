"""Run a model over items with caching and budget control, and load results back offline."""
from __future__ import annotations

import json
from pathlib import Path

from . import client
from .config import CACHE_DIR
from .costs import Ledger, cost_usd, estimate_input_tokens, price_for
from .parsing import parse_response
from .prompts import build_messages, valid_letters


def run_model(items: list[dict], model: str, call_cfg: dict, system_prompt: str, prices: dict,
              ledger: Ledger, overrides: dict | None = None, cache_dir: Path = CACHE_DIR,
              log=print) -> int:
    """Call `model` for every item not already cached. Returns number of new calls."""
    price = price_for(prices, model)
    todo = [it for it in items if not client.cache_path(cache_dir, model, it["id"]).exists()]
    if not todo:
        log(f"[{model}] all {len(items)} items cached, no calls needed")
        return 0
    worst = sum(cost_usd(estimate_input_tokens(build_messages(it, system_prompt)),
                         call_cfg["max_output_tokens"] + 64, price) for it in todo)
    ledger.check(worst)  # raises BudgetError before spending anything
    log(f"[{model}] {len(todo)} calls, worst case ${worst:.4f}, spent so far ${ledger.spent():.4f}")
    for i, it in enumerate(todo, 1):
        payload = client.build_payload(model, build_messages(it, system_prompt), call_cfg, overrides)
        resp, latency = client.chat(payload, call_cfg["timeout_s"], call_cfg["max_retries"])
        ex = client.extract(resp)
        cost = cost_usd(ex["input_tokens"], ex["output_tokens"], price)
        ledger.record(model, it["id"], ex["input_tokens"], ex["output_tokens"], cost)
        p = client.cache_path(cache_dir, model, it["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        params = {k: v for k, v in payload.items() if k != "messages"}
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"item_id": it["id"], "params": params, "latency_s": latency,
                       "response": resp}, f, ensure_ascii=False)
        if i % 10 == 0 or i == len(todo):
            log(f"[{model}] {i}/{len(todo)} done, spent ${ledger.spent():.4f}")
    return len(todo)


def load_side(item: dict, model: str, prices: dict, cache_dir: Path = CACHE_DIR) -> dict | None:
    p = client.cache_path(cache_dir, model, item["id"])
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    ex = client.extract(c["response"])
    parsed = parse_response(ex["content"], ex["token_logprobs"], valid_letters(item))
    return {
        **parsed,
        "correct": bool(parsed["valid"] and parsed["letter"] == item["answer"]),
        "input_tokens": ex["input_tokens"],
        "output_tokens": ex["output_tokens"],
        "reasoning_tokens": ex["reasoning_tokens"],
        "cost": cost_usd(ex["input_tokens"], ex["output_tokens"], price_for(prices, model)),
        "latency": c["latency_s"],
        "finish_reason": ex["finish_reason"],
        "model_returned": ex["model_returned"],
    }


def load_records(items: list[dict], small: str, large: str, prices: dict,
                 cache_dir: Path = CACHE_DIR) -> list[dict]:
    """Join cached small+large outputs. Items missing either side are skipped."""
    out = []
    for it in items:
        s, l = load_side(it, small, prices, cache_dir), load_side(it, large, prices, cache_dir)
        if s and l:
            out.append({"id": it["id"], "level": it["level"], "subject": it["subject"],
                        "country": it["country"], "answer": it["answer"], "small": s, "large": l})
    return out
