"""Unit tests for src/models/candidate_gen.py — no external files required."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.sparse import issparse

from src.models.candidate_gen import ALSCandidateGenerator, build_user_item_matrix


@pytest.fixture()
def train_df() -> pd.DataFrame:
    """Small training DataFrame with deterministic interactions."""
    return pd.DataFrame(
        {
            "customer_id": ["u1", "u1", "u1", "u2", "u2", "u3", "u3", "u3"],
            "article_id": ["a1", "a2", "a3", "a1", "a3", "a2", "a3", "a4"],
            "t_dat": pd.to_datetime(["2020-01-01"] * 8),
            "price": [0.05] * 8,
            "sales_channel_id": [1] * 8,
        }
    )
    # u1: [a1, a2, a3]  u2: [a1, a3]  u3: [a2, a3, a4]


@pytest.fixture()
def fast_gen() -> ALSCandidateGenerator:
    """ALSCandidateGenerator with minimal hyperparams for test speed."""
    return ALSCandidateGenerator(factors=4, iterations=2, regularization=0.1, alpha=40.0)


@pytest.fixture()
def fitted_gen(fast_gen, train_df) -> ALSCandidateGenerator:
    return fast_gen.fit(train_df)


# ── Matrix construction ───────────────────────────────────────────────────────


class TestBuildUserItemMatrix:
    def test_returns_sparse_matrix(self, train_df):
        users = sorted(train_df["customer_id"].unique())
        items = sorted(train_df["article_id"].unique())
        user_index = {u: i for i, u in enumerate(users)}
        item_index = {a: i for i, a in enumerate(items)}
        mat = build_user_item_matrix(train_df, user_index, item_index, alpha=40.0)
        assert issparse(mat)

    def test_shape(self, train_df):
        users = sorted(train_df["customer_id"].unique())
        items = sorted(train_df["article_id"].unique())
        user_index = {u: i for i, u in enumerate(users)}
        item_index = {a: i for i, a in enumerate(items)}
        mat = build_user_item_matrix(train_df, user_index, item_index)
        assert mat.shape == (3, 4)

    def test_confidence_values_greater_than_one(self, train_df):
        users = sorted(train_df["customer_id"].unique())
        items = sorted(train_df["article_id"].unique())
        user_index = {u: i for i, u in enumerate(users)}
        item_index = {a: i for i, a in enumerate(items)}
        mat = build_user_item_matrix(train_df, user_index, item_index, alpha=40.0)
        assert (mat.data > 1.0).all()

    def test_alpha_zero_gives_ones(self, train_df):
        users = sorted(train_df["customer_id"].unique())
        items = sorted(train_df["article_id"].unique())
        user_index = {u: i for i, u in enumerate(users)}
        item_index = {a: i for i, a in enumerate(items)}
        mat = build_user_item_matrix(train_df, user_index, item_index, alpha=0.0)
        np.testing.assert_allclose(mat.data, np.ones_like(mat.data))


# ── Fit ───────────────────────────────────────────────────────────────────────


class TestFit:
    def test_returns_self(self, fast_gen, train_df):
        assert fast_gen.fit(train_df) is fast_gen

    def test_fitted_flag(self, fitted_gen):
        assert fitted_gen._fitted is True

    def test_n_users(self, fitted_gen):
        assert fitted_gen.n_users == 3

    def test_n_items(self, fitted_gen):
        assert fitted_gen.n_items == 4

    def test_user_index_keys(self, fitted_gen):
        assert set(fitted_gen._user_index.keys()) == {"u1", "u2", "u3"}

    def test_item_index_keys(self, fitted_gen):
        assert set(fitted_gen._item_index.keys()) == {"a1", "a2", "a3", "a4"}

    def test_item_reverse_is_inverse(self, fitted_gen):
        for article_id, col in fitted_gen._item_index.items():
            assert fitted_gen._item_reverse[col] == article_id

    def test_empty_train_raises(self, fast_gen):
        empty = pd.DataFrame(columns=["customer_id", "article_id"])
        with pytest.raises(ValueError, match="empty"):
            fast_gen.fit(empty)

    def test_missing_column_raises(self, fast_gen):
        with pytest.raises(ValueError, match="customer_id"):
            fast_gen.fit(pd.DataFrame({"article_id": ["a1"]}))

    def test_unfitted_raises_on_n_users(self, fast_gen):
        with pytest.raises(RuntimeError, match="not been fitted"):
            _ = fast_gen.n_users


# ── Recommend ─────────────────────────────────────────────────────────────────


class TestRecommend:
    def test_returns_list(self, fitted_gen):
        recs = fitted_gen.recommend("u1", k=4)
        assert isinstance(recs, list)

    def test_length_at_most_k(self, fitted_gen):
        # 4 items total; k is an upper bound — can never exceed n_items
        recs = fitted_gen.recommend("u1", k=10, exclude_seen=False)
        assert len(recs) <= 4

    def test_no_duplicates(self, fitted_gen):
        recs = fitted_gen.recommend("u1", k=4, exclude_seen=False)
        assert len(recs) == len(set(recs))

    def test_exclude_seen_removes_training_items(self, fitted_gen):
        # u2 purchased a1, a3 in train; a2 and a4 are unseen
        recs = fitted_gen.recommend("u2", k=10, exclude_seen=True)
        assert "a1" not in recs
        assert "a3" not in recs

    def test_include_seen_returns_training_items(self, fitted_gen):
        recs = fitted_gen.recommend("u1", k=4, exclude_seen=False)
        seen = {"a1", "a2", "a3"}
        assert any(r in seen for r in recs)

    def test_unknown_user_raises_key_error(self, fitted_gen):
        with pytest.raises(KeyError, match="Unknown user"):
            fitted_gen.recommend("nonexistent_user")

    def test_unfitted_raises_runtime_error(self, fast_gen):
        with pytest.raises(RuntimeError, match="not been fitted"):
            fast_gen.recommend("u1")

    def test_all_returned_items_in_vocabulary(self, fitted_gen):
        recs = fitted_gen.recommend("u2", k=10, exclude_seen=False)
        vocab = set(fitted_gen._item_index.keys())
        assert all(r in vocab for r in recs)


# ── Save / Load ───────────────────────────────────────────────────────────────


class TestSaveLoad:
    def test_roundtrip_n_users_n_items(self, fitted_gen):
        with tempfile.NamedTemporaryFile(suffix=".joblib") as f:
            fitted_gen.save(f.name)
            gen2 = ALSCandidateGenerator.load(f.name)
        assert gen2.n_users == fitted_gen.n_users
        assert gen2.n_items == fitted_gen.n_items

    def test_roundtrip_recommendations_match(self, fitted_gen):
        recs_before = fitted_gen.recommend("u2", k=3, exclude_seen=False)
        with tempfile.NamedTemporaryFile(suffix=".joblib") as f:
            fitted_gen.save(f.name)
            gen2 = ALSCandidateGenerator.load(f.name)
        recs_after = gen2.recommend("u2", k=3, exclude_seen=False)
        assert recs_before == recs_after

    def test_save_creates_parent_dirs(self, fitted_gen):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "subdir" / "model.joblib"
            fitted_gen.save(path)
            assert path.exists()

    def test_load_hyperparams_preserved(self, fitted_gen):
        with tempfile.NamedTemporaryFile(suffix=".joblib") as f:
            fitted_gen.save(f.name)
            gen2 = ALSCandidateGenerator.load(f.name)
        assert gen2.factors == fitted_gen.factors
        assert gen2.alpha == fitted_gen.alpha
