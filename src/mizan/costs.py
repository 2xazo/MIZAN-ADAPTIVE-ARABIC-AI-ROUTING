"""Cost formula, pre-batch worst-case estimates, and a persistent spend ledger."""
from __future__ import annotations

import json
import time
from pathlib import Path


class BudgetError(RuntimeError):
    pass


def price_for(prices: dict, model: str) -> dict:
    p = prices["models"].get(model)
    if not p or p.get("input") is None or p.get("output") is None:
        raise BudgetError(f"No verified price for {model} in config/prices.yaml")
    return p


def cost_usd(input_tokens: int, output_tokens: int, price: dict) -> float:
    return input_tokens / 1_000_000 * price["input"] + output_tokens / 1_000_000 * price["output"]


def estimate_input_tokens(messages: list[dict]) -> int:
    """Deliberately pessimistic: ~1 token per 1.5 chars of Arabic + per-message overhead."""
    chars = sum(len(m["content"]) for m in messages)
    return int(chars / 1.5) + 12 * len(messages) + 10


def require_verified(prices: dict) -> None:
    if not prices.get("verified"):
        raise BudgetError(
            "config/prices.yaml is not verified. Check the official pricing page, update the "
            "numbers, set verified: true and verified_on: YYYY-MM-DD, then rerun.")


class Ledger:
    """Append-only record of actual spend. Survives restarts."""

    def __init__(self, path: Path, limit_usd: float):
        self.path = Path(path)
        self.limit = limit_usd

    def spent(self) -> float:
        if not self.path.exists():
            return 0.0
        with open(self.path, encoding="utf-8") as f:
            return sum(json.loads(l)["cost_usd"] for l in f if l.strip())

    def check(self, worst_case_usd: float) -> None:
        spent = self.spent()
        if spent + worst_case_usd > self.limit:
            raise BudgetError(
                f"Batch worst case ${worst_case_usd:.4f} + spent ${spent:.4f} exceeds "
                f"experiment limit ${self.limit:.2f}. Stopping (reserve needs coordinator approval).")

    def record(self, model: str, item_id: str, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "model": model, "item_id": item_id,
                                "input_tokens": input_tokens, "output_tokens": output_tokens,
                                "cost_usd": cost}) + "\n")
