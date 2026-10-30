"""AUROC (rank-based, tie-aware, no sklearn) and bootstrap confidence intervals."""
from __future__ import annotations

from typing import Callable

import numpy as np


def auroc(scores, labels) -> float | None:
    """P(score of a correct item > score of an incorrect item), ties count 0.5.
    Infinite scores are allowed. Returns None if one class is empty."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    # Ranks over all items with average ranks for ties (inf-safe via argsort on order keys).
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    r_pos = ranks[y].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def bootstrap_ci(n: int, stat: Callable[[np.ndarray], float], iters: int = 1000,
                 seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI of `stat(indices)` over resampled item indices."""
    rng = np.random.default_rng(seed)
    vals = [stat(rng.integers(0, n, size=n)) for _ in range(iters)]
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
