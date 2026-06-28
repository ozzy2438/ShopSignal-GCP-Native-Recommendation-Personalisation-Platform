"""Unit tests for src/models/popularity.py — no external files required."""

from __future__ import annotations

import pandas as pd
import pytest

from src.models.popularity import PopularityRecommender


@pytest.fixture()
def train_df() -> pd.DataFrame:
    """Small training DataFrame with known purchase frequencies."""
    return pd.DataFrame(
        {
            "customer_id": ["u1", "u1", "u1", "u2", "u2", "u3"],
            "article_id": ["a1", "a2", "a1", "a1", "a3", "a2"],
            "t_dat": pd.to_datetime(["2020-01-01"] * 6),
            "price": [0.05] * 6,
            "sales_channel_id": [1] * 6,
        }
    )
    # a1: 3 purchases, a2: 2 purchases, a3: 1 purchase


class TestFit:
    def test_fit_returns_self(self, train_df):
        model = PopularityRecommender()
        assert model.fit(train_df) is model

    def test_n_articles(self, train_df):
        model = PopularityRecommender().fit(train_df)
        assert model.n_articles == 3

    def test_unfitted_raises(self):
        with pytest.raises(RuntimeError, match="not been fitted"):
            PopularityRecommender().top_k()

    def test_empty_train_raises(self):
        empty = pd.DataFrame(columns=["customer_id", "article_id"])
        with pytest.raises(ValueError, match="empty"):
            PopularityRecommender().fit(empty)

    def test_missing_article_id_raises(self):
        with pytest.raises(ValueError, match="article_id"):
            PopularityRecommender().fit(pd.DataFrame({"customer_id": ["u1"]}))


class TestTopK:
    def test_top_k_order(self, train_df):
        model = PopularityRecommender().fit(train_df)
        top = model.top_k(3)
        assert top[0] == "a1"
        assert top[1] == "a2"
        assert top[2] == "a3"

    def test_top_k_length(self, train_df):
        model = PopularityRecommender().fit(train_df)
        assert len(model.top_k(2)) == 2

    def test_top_k_fewer_than_k_articles(self, train_df):
        model = PopularityRecommender().fit(train_df)
        top = model.top_k(100)
        assert len(top) == 3  # only 3 unique articles

    def test_top_k_cached(self, train_df):
        model = PopularityRecommender().fit(train_df)
        top1 = model.top_k(3)
        top2 = model.top_k(3)
        assert top1 is top2  # same list object from cache


class TestRecommend:
    def test_known_user_exclude_seen(self, train_df):
        model = PopularityRecommender().fit(train_df)
        recs = model.recommend("u1", k=10, exclude_seen=True)
        # u1 has seen a1, a2 → only a3 remains
        assert "a1" not in recs
        assert "a2" not in recs
        assert "a3" in recs

    def test_known_user_include_seen(self, train_df):
        model = PopularityRecommender().fit(train_df)
        recs = model.recommend("u1", k=3, exclude_seen=False)
        assert recs == ["a1", "a2", "a3"]

    def test_cold_start_user_gets_global_top_k(self, train_df):
        model = PopularityRecommender().fit(train_df)
        recs = model.recommend("unknown_user", k=2)
        assert recs == ["a1", "a2"]

    def test_recommend_length_at_most_k(self, train_df):
        model = PopularityRecommender().fit(train_df)
        assert len(model.recommend("u1", k=2)) <= 2

    def test_recommend_returns_list(self, train_df):
        model = PopularityRecommender().fit(train_df)
        assert isinstance(model.recommend("u1"), list)

    def test_recommendations_are_unique(self, train_df):
        model = PopularityRecommender().fit(train_df)
        recs = model.recommend("u2", k=10)
        assert len(recs) == len(set(recs))
