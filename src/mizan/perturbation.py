"""Option-order perturbation test: same questions and option texts, new option order.

This is NOT a new held-out set, unseen questions, or out-of-domain data. Each item keeps its id so
it pairs with the original run. Responses are cached separately (PERTURBATION_CACHE_DIR), because
the id alone would otherwise return the original answers from the cache.
"""
from __future__ import annotations

import random
import re

from .data import LETTERS

PERTURBATION_SEED = 20261030
MAX_DRAWS = 1000

# Option text that depends on position or on other options. Flagged and counted, never removed.
POSITION_DEPENDENT = re.compile(r"ما\s?سبق|ما\s?ذكر|ما\s?تقدم|(?<!\S)الجميع(?!\S)"
                                r"|\b(all|none|both) of (the|these|those)\b"
                                r"|(?<!\S)[أبجده]\s+و\s*[أبجده](?!\S)|\b[A-E]\s+(and|&)\s+[A-E]\b",
                                re.IGNORECASE)


def item_rng(item_id: str, seed: int) -> random.Random:
    """Per-item generator, so one item's order does not depend on the file order."""
    return random.Random(f"{seed}:{item_id}")


def permutation_for(options: list[str], item_id: str, seed: int = PERTURBATION_SEED) -> tuple[list[int], bool]:
    """Fisher-Yates (random.shuffle), redrawn until the displayed text order changes.
    Returns (perm, changed), where perm[new_position] = old_position. `changed` is False only when
    no order can differ, which happens when every option text is the same."""
    n = len(options)
    perm = list(range(n))
    if len(set(options)) < 2:
        item_rng(item_id, seed).shuffle(perm)
        return perm, False
    rng = item_rng(item_id, seed)
    for _ in range(MAX_DRAWS):
        rng.shuffle(perm)
        if [options[i] for i in perm] != options:
            return perm, True
    raise RuntimeError(f"no changed order found for item {item_id}")


def perturb_item(item: dict, seed: int = PERTURBATION_SEED) -> dict:
    options = item["options"]
    perm, changed = permutation_for(options, item["id"], seed)
    old_index = LETTERS.index(item["answer"])
    out = {**item, "options": [options[i] for i in perm], "answer": LETTERS[perm.index(old_index)],
           "original_answer": item["answer"], "option_permutation": perm, "order_changed": changed,
           "position_dependent_option": any(POSITION_DEPENDENT.search(o) for o in options),
           "perturbation_seed": seed}
    verify_item(item, out)
    return out


def verify_item(original: dict, shuffled: dict) -> None:
    """Raises on any broken guarantee. Uses `raise`, so it still runs under python -O."""
    def check(ok: bool, what: str) -> None:
        if not ok:
            raise AssertionError(f"item {original['id']}: {what}")
    check(shuffled["id"] == original["id"], "id changed")
    check(shuffled["question"] == original["question"], "question text changed")
    check(shuffled.get("context") == original.get("context"), "context changed")
    check(len(shuffled["options"]) == len(original["options"]), "number of options changed")
    check(sorted(shuffled["options"]) == sorted(original["options"]), "option texts changed")
    old = original["options"][LETTERS.index(original["answer"])]
    new = shuffled["options"][LETTERS.index(shuffled["answer"])]
    check(old == new, "correct answer text changed")
    check(LETTERS.index(shuffled["answer"]) < len(shuffled["options"]), "answer letter out of range")


def perturb_items(items: list[dict], seed: int = PERTURBATION_SEED) -> tuple[list[dict], dict]:
    out = [perturb_item(it, seed) for it in items]
    manifest = {"name": "Option-order perturbation test", "seed": seed,
                "algorithm": "random.Random(f'{seed}:{id}').shuffle, redrawn until the text order changes",
                "n": len(out), "stayed_identical": sum(not o["order_changed"] for o in out),
                "answer_letter_changed": sum(o["answer"] != o["original_answer"] for o in out),
                "position_dependent_option": sum(o["position_dependent_option"] for o in out)}
    return out, manifest
