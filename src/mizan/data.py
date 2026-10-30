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


def stratified_split(items: list[dict], dev_size: int, heldout_size: int, seed: int,
                     keys: Iterable[str] = ("subject", "level")) -> tuple[list[dict], list[dict]]:
    """Proportional stratified sample of disjoint Dev and Held-out sets.

    Each stratum is shuffled with the fixed seed, then items are dealt round-robin across
    strata (largest first) so both splits cover all subjects/levels in proportion.
    """
    keys = tuple(keys)
    rng = random.Random(seed)
    strata: dict[tuple, list[dict]] = defaultdict(list)
    for it in sorted(items, key=lambda x: x["id"]):
        strata[tuple(it[k] for k in keys)].append(it)
    for k in sorted(strata):
        rng.shuffle(strata[k])
    order = sorted(strata, key=lambda k: (-len(strata[k]), k))
    dealt: list[dict] = []
    depth = 0
    while any(depth < len(strata[k]) for k in order):
        for k in order:
            if depth < len(strata[k]):
                dealt.append(strata[k][depth])
        depth += 1
    need = dev_size + heldout_size
    if need > len(dealt):
        raise ValueError(f"need {need} items, only {len(dealt)} valid")
    pool = dealt[:need]
    # Evenly interleave assignment (Bresenham-style) so both splits stay stratified.
    dev, held = [], []
    for i, it in enumerate(pool):
        if (i + 1) * heldout_size // need > i * heldout_size // need:
            held.append(it)
        else:
            dev.append(it)
    assert not {d["id"] for d in dev} & {h["id"] for h in held}
    return dev, held


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
