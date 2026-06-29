"""Unit tests for src/features/ranking_dataset.py — leakage-safe construction."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.build_features import FEATURE_COLS
from src.features.ranking_dataset import build_candidate_pairs, build_ranking_dataset


@pytest.fixture()
def train_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["u1", "u1", "u2", "u2", "u3"],
            "article_id": ["a1", "a2", "a1", "a3", "a4"],
            "price": [0.1, 0.2, 0.3, 0.4, 0.5],
            "sales_channel_id": [1, 2, 1, 1, 2],
            "t_dat": pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"]
            ),
        }
    )


@pytest.fixture()
def candidates() -> dict[str, list[str]]:
    return {"u1": ["a3", "a4", "a5"], "u2": ["a2", "a4", "a5"], "u3": ["a1", "a2", "a3"]}


def test_candidate_pairs_rank_and_seen(train_df, candidates):
    seen = {"u1": {"a1", "a2"}}
    pairs = build_candidate_pairs(candidates, seen)
    u1 = pairs[pairs.customer_id == "u1"].sort_values("als_rank")
    assert list(u1.als_rank) == [0, 1, 2]
    assert (u1.als_score.diff().dropna() < 0).all()  # score monotone decreasing with rank


def test_groups_sum_to_rows(train_df, candidates):
    labels = {"u1": {"a3"}, "u2": {"a2", "a4"}, "u3": {"a3"}}
    ds = build_ranking_dataset(candidates, train_df, labels, max_negatives=10, seed=1)
    assert sum(ds.group) == len(ds.X)
    assert len(ds.y) == len(ds.X)
    assert list(ds.X.columns) == FEATURE_COLS


def test_labels_aligned_with_positives(train_df, candidates):
    labels = {"u1": {"a3"}, "u2": {"a2", "a4"}, "u3": {"a3"}}
    ds = build_ranking_dataset(candidates, train_df, labels, max_negatives=10, seed=1)
    # u3 has positive a3, u1 positive a3, u2 positives a2+a4 -> 4 positives total
    assert ds.y.sum() == 4


def test_user_without_positive_dropped(train_df):
    cands = {"u1": ["a9", "a8"]}  # neither bought in label window
    ds = build_ranking_dataset(cands, train_df, {"u1": {"zzz"}}, seed=1)
    assert len(ds.X) == 0
    assert ds.group == []


def test_deterministic_sampling(train_df):
    cands = {"u1": [f"i{i}" for i in range(100)]}
    labels = {"u1": {"i0"}}
    a = build_ranking_dataset(cands, train_df, labels, max_negatives=5, seed=7)
    b = build_ranking_dataset(cands, train_df, labels, max_negatives=5, seed=7)
    assert np.array_equal(a.y, b.y)
    assert a.X.reset_index(drop=True).equals(b.X.reset_index(drop=True))
