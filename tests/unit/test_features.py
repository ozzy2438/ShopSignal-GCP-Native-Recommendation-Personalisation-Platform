"""Unit tests for src/features/build_features.py — fixtures only, no I/O."""

from __future__ import annotations

import pandas as pd
import pytest

from src.features.build_features import (
    FEATURE_COLS,
    ITEM_FEATURE_COLS,
    USER_FEATURE_COLS,
    assemble_feature_matrix,
    build_item_features,
    build_user_features,
    user_seen_items,
)


@pytest.fixture()
def train_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["u1", "u1", "u1", "u2", "u2", "u3"],
            "article_id": ["a1", "a2", "a1", "a1", "a3", "a2"],
            "price": [0.10, 0.20, 0.10, 0.30, 0.40, 0.50],
            "sales_channel_id": [1, 1, 2, 1, 2, 1],
            "t_dat": pd.to_datetime(
                ["2020-01-01", "2020-01-03", "2020-01-05", "2020-01-02", "2020-01-08", "2020-01-04"]
            ),
        }
    )


def test_item_features_schema(train_df):
    feats = build_item_features(train_df)
    assert list(feats.columns) == ITEM_FEATURE_COLS
    assert (feats.dtypes == "float32").all()


def test_item_purchase_count_and_buyers(train_df):
    feats = build_item_features(train_df)
    assert feats.loc["a1", "item_purchase_count"] == 3
    assert feats.loc["a1", "item_unique_buyers"] == 2  # u1, u2
    assert feats["item_popularity_score"].max() == pytest.approx(1.0)


def test_user_features_schema(train_df):
    feats = build_user_features(train_df)
    assert list(feats.columns) == USER_FEATURE_COLS
    assert (feats.dtypes == "float32").all()


def test_user_channel_ratio(train_df):
    feats = build_user_features(train_df)
    # u1: 2 online / 1 store -> 2/3; u2: 1 online / 1 store -> 0.5
    assert feats.loc["u1", "user_online_ratio"] == pytest.approx(2 / 3, rel=1e-4)
    assert feats.loc["u2", "user_online_ratio"] == pytest.approx(0.5)


def test_assemble_matrix_has_exact_feature_cols(train_df):
    pairs = pd.DataFrame(
        {
            "customer_id": ["u1", "u1"],
            "article_id": ["a1", "a2"],
            "als_score": [2.0, 1.0],
            "als_rank": [0, 1],
            "ui_user_bought_item": [1.0, 1.0],
        }
    )
    m = assemble_feature_matrix(pairs, build_item_features(train_df), build_user_features(train_df))
    assert list(m.columns) == FEATURE_COLS
    assert not m.isna().any().any()


def test_unknown_item_filled_with_zero(train_df):
    pairs = pd.DataFrame(
        {
            "customer_id": ["u1"],
            "article_id": ["zzz"],
            "als_score": [1.0],
            "als_rank": [0],
            "ui_user_bought_item": [0.0],
        }
    )
    m = assemble_feature_matrix(pairs, build_item_features(train_df), build_user_features(train_df))
    assert m.loc[0, "item_purchase_count"] == 0


def test_user_seen_items(train_df):
    assert user_seen_items(train_df)["u1"] == {"a1", "a2"}
