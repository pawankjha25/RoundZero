"""
Gate metrics (specs/005, design doc "Evaluation and metrics"). Pure functions,
no I/O - evals/world_model/gates.py feeds them reviewed labels.
"""
from __future__ import annotations

import math
import re


def quadratic_weighted_kappa(a: list[int], b: list[int], n_levels: int = 4) -> float:
    """Agreement between two ordinal raters (system vs reviewed label).
    1.0 = perfect, 0 = chance. Returns 0.0 for an empty or degenerate input."""
    if not a or len(a) != len(b):
        return 0.0
    n = len(a)
    observed = [[0.0] * n_levels for _ in range(n_levels)]
    for x, y in zip(a, b):
        observed[x][y] += 1
    hist_a = [sum(observed[i]) for i in range(n_levels)]
    hist_b = [sum(observed[i][j] for i in range(n_levels)) for j in range(n_levels)]
    num = den = 0.0
    for i in range(n_levels):
        for j in range(n_levels):
            w = ((i - j) ** 2) / ((n_levels - 1) ** 2)
            expected = hist_a[i] * hist_b[j] / n
            num += w * observed[i][j]
            den += w * expected
    if den == 0:
        return 1.0 if num == 0 else 0.0
    return 1.0 - num / den


def expected_calibration_error(confidences: list[float], correct: list[bool], bins: int = 10) -> float:
    if not confidences:
        return 0.0
    total = len(confidences)
    ece = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (lo < c <= hi) or (b == 0 and c == 0)]
        if not idx:
            continue
        acc = sum(1 for i in idx if correct[i]) / len(idx)
        conf = sum(confidences[i] for i in idx) / len(idx)
        ece += len(idx) / total * abs(acc - conf)
    return ece


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _overlaps(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    return bool(a) and bool(b) and (a in b or b in a)


def span_precision_recall(
    predicted: list[tuple[int, str, str]], gold: list[tuple[int, str, str]]
) -> tuple[float, float]:
    """Items are (turn_index, polarity, span). A predicted item matches a gold
    item on the same turn and polarity whose span overlaps it (substring either
    way). `absent` items (span None/"") match on turn + polarity alone."""

    def match(p, g) -> bool:
        if p[0] != g[0] or p[1] != g[1]:
            return False
        if p[1] == "absent":
            return True
        return _overlaps(p[2], g[2])

    tp_pred = sum(1 for p in predicted if any(match(p, g) for g in gold))
    tp_gold = sum(1 for g in gold if any(match(p, g) for p in predicted))
    precision = tp_pred / len(predicted) if predicted else 0.0
    recall = tp_gold / len(gold) if gold else 0.0
    return precision, recall


def mean_log_loss(probabilities: list[float]) -> float:
    """Mean negative log-likelihood of observed outcomes (lower is better)."""
    if not probabilities:
        return 0.0
    return -sum(math.log(max(p, 1e-9)) for p in probabilities) / len(probabilities)
