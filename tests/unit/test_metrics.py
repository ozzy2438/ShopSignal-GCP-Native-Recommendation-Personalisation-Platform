"""Unit tests for src/evaluate/metrics.py — no external dependencies."""

import pytest

from src.evaluate.metrics import map_at_k, ndcg_at_k, recall_at_k


# ── NDCG@K ───────────────────────────────────────────────────────────────────
class TestNdcgAtK:
    def test_perfect_ranking(self):
        """When all top-k items are relevant the score should be 1.0."""
        recommended = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        assert ndcg_at_k(recommended, relevant, k=3) == pytest.approx(1.0)

    def test_no_relevant_items(self):
        """When there are no ground-truth items the score should be 0.0."""
        assert ndcg_at_k(["a", "b"], set(), k=10) == 0.0

    def test_no_hits(self):
        """When recommended items are completely wrong the score should be 0.0."""
        assert ndcg_at_k(["x", "y"], {"a", "b"}, k=10) == 0.0

    def test_partial_ranking(self):
        """Partial overlap should yield a score between 0 and 1."""
        score = ndcg_at_k(["a", "x", "b"], {"a", "b"}, k=3)
        assert 0.0 < score < 1.0

    def test_position_matters(self):
        """A hit at position 1 should score higher than a hit at position 3."""
        score_top = ndcg_at_k(["a", "x", "x"], {"a"}, k=3)
        score_bottom = ndcg_at_k(["x", "x", "a"], {"a"}, k=3)
        assert score_top > score_bottom


# ── Recall@K ─────────────────────────────────────────────────────────────────
class TestRecallAtK:
    def test_perfect_recall(self):
        assert recall_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == pytest.approx(1.0)

    def test_zero_recall(self):
        assert recall_at_k(["x", "y"], {"a", "b"}, k=10) == 0.0

    def test_empty_relevant(self):
        assert recall_at_k(["a"], set(), k=5) == 0.0

    def test_partial_recall(self):
        score = recall_at_k(["a", "x", "x"], {"a", "b"}, k=3)
        assert score == pytest.approx(0.5)


# ── MAP@K ─────────────────────────────────────────────────────────────────────
class TestMapAtK:
    def test_perfect_map(self):
        assert map_at_k(["a", "b"], {"a", "b"}, k=2) == pytest.approx(1.0)

    def test_zero_map(self):
        assert map_at_k(["x", "y"], {"a", "b"}, k=5) == 0.0

    def test_empty_relevant(self):
        assert map_at_k(["a"], set(), k=5) == 0.0
