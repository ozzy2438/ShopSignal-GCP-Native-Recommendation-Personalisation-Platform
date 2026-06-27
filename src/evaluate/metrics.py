"""
Evaluation metrics for the ShopSignal recommendation engine.

Metrics implemented
-------------------
- ndcg_at_k   : Normalised Discounted Cumulative Gain
- recall_at_k : Fraction of relevant items retrieved in top-k
- map_at_k    : Mean Average Precision at k

These functions operate on plain Python lists and have no external
dependencies so they can be unit-tested in CI without GCP credentials.

TODO(feat/two-stage-model): plug these into the LightGBM evaluation
callback and the MLOps promotion gate.
"""

from __future__ import annotations

import math


def dcg_at_k(relevant_flags: list[int], k: int) -> float:
    """Discounted Cumulative Gain for a single query."""
    return sum(rel / math.log2(idx + 2) for idx, rel in enumerate(relevant_flags[:k]))


def ndcg_at_k(recommended: list[str], relevant: set[str], k: int = 10) -> float:
    """
    Normalised DCG for a single user.

    Parameters
    ----------
    recommended : ordered list of article_ids (best first)
    relevant    : ground-truth set of article_ids the user interacted with
    k           : cut-off rank
    """
    if not relevant:
        return 0.0

    flags = [1 if item in relevant else 0 for item in recommended[:k]]
    actual = dcg_at_k(flags, k)

    ideal_flags = [1] * min(len(relevant), k)
    ideal = dcg_at_k(ideal_flags, k)

    return actual / ideal if ideal > 0 else 0.0


def recall_at_k(recommended: list[str], relevant: set[str], k: int = 10) -> float:
    """Fraction of relevant items that appear in the top-k recommendations."""
    if not relevant:
        return 0.0
    hits = sum(1 for item in recommended[:k] if item in relevant)
    return hits / len(relevant)


def map_at_k(recommended: list[str], relevant: set[str], k: int = 10) -> float:
    """Mean Average Precision at k for a single user."""
    if not relevant:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for idx, item in enumerate(recommended[:k]):
        if item in relevant:
            hits += 1
            precision_sum += hits / (idx + 1)
    return precision_sum / min(len(relevant), k)
