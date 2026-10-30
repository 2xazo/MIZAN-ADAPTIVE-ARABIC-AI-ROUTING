"""ArabicMMLU normalization and a fixed-seed, stratified Dev/Held-out split."""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable

LETTERS = "ABCDE"
# Arabic option labels sometimes used in exams -> ASCII
ARABIC_TO_ASCII = {"أ": "A", "ا": "A", "ب": "B", "ج": "C", "د": "D", "ه": "E", "هـ": "E"}


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == ""


def normalize_answer_key(key, n_options: int) -> str | None:
    """Return 'A'..'E' or None if the key cannot be mapped to an existing option."""
    if _blank(key):
        return None
    k = str(key).strip()
    if k in ARABIC_TO_ASCII:
        k = ARABIC_TO_ASCII[k]
    elif k.isdigit():
        i = int(k)
        k = LETTERS[i - 1] if 1 <= i <= 5 else ""
    k = k.upper()
    if len(k) == 1 and k in LETTERS[:n_options]:
        return k
    return None


def normalize_row(row: dict) -> tuple[dict | None, str | None]:
    """Map one raw ArabicMMLU row to the internal schema. Returns (item, reject_reason)."""
    options = []
    for i in range(1, 6):
        v = row.get(f"Option {i}")
        if _blank(v):
            break
        options.append(str(v).strip())
    if len(options) < 2:
        return None, "fewer_than_2_options"
    if _blank(row.get("Question")):
        return None, "empty_question"
    answer = normalize_answer_key(row.get("Answer Key"), len(options))
    if answer is None:
        return None, "unmappable_answer_key"
    return {
        "id": str(row.get("ID")),
        "subject": str(row.get("Subject", "")),
        "level": str(row.get("Level", "")),
        "country": str(row.get("Country", "")),
        "group": str(row.get("Group", "")),
        "question": str(row["Question"]).strip(),
        "context": "" if _blank(row.get("Context")) else str(row["Context"]).strip(),
        "options": options,
        "answer": answer,
    }, None


def _heldout_allocation(sizes: dict, heldout_size: int, need: int) -> dict:
    """Held-out count per stratum, proportional and summing exactly to `heldout_size`.

    A stratum with at least two items keeps an item on each side unless the sizes make that impossible.
    """
    def low(k):
        return 1 if sizes[k] >= 2 else 0

    def high(k):
        return sizes[k] - 1 if sizes[k] >= 2 else sizes[k]

    exact = {k: m * heldout_size / need for k, m in sizes.items()}
    alloc = {k: min(max(math.floor(exact[k]), low(k)), high(k)) for k in sizes}
    ranked = sorted(sizes, key=lambda k: (math.floor(exact[k]) - exact[k], k))  # largest remainder first
    left = heldout_size - sum(alloc.values())
    while left > 0:
        room = [k for k in ranked if alloc[k] < high(k)] or [k for k in ranked if alloc[k] < sizes[k]]
        for k in room[:left]:
            alloc[k] += 1
            left -= 1
    while left < 0:
        room = [k for k in reversed(ranked) if alloc[k] > low(k)] or [k for k in reversed(ranked) if alloc[k] > 0]
        for k in room[:-left]:
            alloc[k] -= 1
            left += 1
    return alloc


def stratified_split(items: list[dict], dev_size: int, heldout_size: int, seed: int,
                     keys: Iterable[str] = ("subject", "level")) -> tuple[list[dict], list[dict]]:
    """Stratified sample of disjoint Dev and Held-out sets whose strata are shared.

    Each stratum is shuffled with the fixed seed, then items are dealt round-robin across strata
    (largest first), so the pool is equal-depth per stratum, not proportional to the dataset. Each
    stratum is then divided between the two splits on its own, so the assignment cannot alias with
    the number of strata.

    Every reported MIZAN result uses the original split in artifacts/split_ids.json, built before
    this fix. See docs/decisions.md.
    """
    keys = tuple(keys)
    rng = random.Random(seed)
    strata: dict[tuple, list[dict]] = defaultdict(list)
    for it in sorted(items, key=lambda x: x["id"]):
        strata[tuple(it[k] for k in keys)].append(it)
    for k in sorted(strata):
        rng.shuffle(strata[k])
    order = sorted(strata, key=lambda k: (-len(strata[k]), k))
    dealt: list[tuple[tuple, dict]] = []
    depth = 0
    while any(depth < len(strata[k]) for k in order):
        for k in order:
            if depth < len(strata[k]):
                dealt.append((k, strata[k][depth]))
        depth += 1
    need = dev_size + heldout_size
    if need > len(dealt):
        raise ValueError(f"need {need} items, only {len(dealt)} valid")
    pool = dealt[:need]
    sizes: dict[tuple, int] = defaultdict(int)
    for k, _ in pool:
        sizes[k] += 1
    alloc = _heldout_allocation(sizes, heldout_size, need)
    # Evenly interleave assignment (Bresenham-style) inside each stratum.
    dev, held = [], []
    seen: dict[tuple, int] = defaultdict(int)
    for k, it in pool:
        j = seen[k]
        seen[k] += 1
        if (j + 1) * alloc[k] // sizes[k] > j * alloc[k] // sizes[k]:
            held.append(it)
        else:
            dev.append(it)
    assert not {d["id"] for d in dev} & {h["id"] for h in held}
    return dev, held


def select_by_ids(items: list[dict], ids: list[str]) -> list[dict]:
    """Items in the exact order of a recorded ID list. Raises if an ID is missing."""
    by_id = {it["id"]: it for it in items}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise ValueError(f"{len(missing)} recorded IDs are not in the dataset, first: {missing[0]}")
    return [by_id[i] for i in ids]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
