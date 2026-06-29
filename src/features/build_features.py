"""
Feature engineering for the LightGBM ranker — Stage 2 of the pipeline.

Design
------
The LightGBM ranker re-ranks the top-200 ALS candidates per user.  To do
that it needs a feature matrix where each row is a (user, candidate-item)
pair.  The features fall into three families:

  * item features  — popularity, purchase count, unique buyers, avg price,
                     recency (mirrors dbt fct_item_features)
  * user features  — purchase count, unique items, spend, activity span,
                     online/offline channel ratio (mirrors fct_user_features)
  * als features   — als_score, als_rank (supplied by the candidate stage)

Leakage safety
--------------
ALL features here are computed from the TRAINING split only.  The ranker is
trained against labels from the validation period and evaluated on the test
period, so any feature derived from train rows is strictly "before the label
period" and cannot leak future information.  Callers must pass train-only
transactions to build_*_features.  This is the same contract ALS and the
popularity baseline already honour.

Features are computed in pure pandas so they are testable in CI without
BigQuery or GCP credentials.  The dbt marts (fct_user_features /
fct_item_features) remain the production source; column names and dtypes
here are kept consistent with them.

TODO(feat/data-pipeline): a future PR can swap the pandas compute for a
BigQuery read of the dbt marts behind the same function signatures.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Feature schema — names and dtypes must stay consistent across train/predict.
ITEM_FEATURE_COLS: list[str] = [
    "item_unique_buyers",
    "item_purchase_count",
    "item_avg_price",
    "item_popularity_score",
    "item_recency_days",
]
USER_FEATURE_COLS: list[str] = [
    "user_purchase_count",
    "user_unique_items",
    "user_total_spend",
    "user_avg_spend",
    "user_active_days",
    "user_recency_days",
    "user_online_ratio",
]
INTERACTION_FEATURE_COLS: list[str] = [
    "als_score",
    "als_rank",
    "ui_user_bought_item",
]

FEATURE_COLS: list[str] = ITEM_FEATURE_COLS + USER_FEATURE_COLS + INTERACTION_FEATURE_COLS


def build_item_features(train: pd.DataFrame) -> pd.DataFrame:
    """Compute item-level features from the training split.

    Mirrors dbt fct_item_features.  recency is measured relative to the last
    transaction in train, so it never references future data.

    Parameters
    ----------
    train : Training transactions with article_id, customer_id, price, t_dat.

    Returns
    -------
    DataFrame indexed by article_id with ITEM_FEATURE_COLS (float32).
    """
    ref_date = train["t_dat"].max()
    grp = train.groupby("article_id")
    feats = pd.DataFrame(
        {
            "item_unique_buyers": grp["customer_id"].nunique(),
            "item_purchase_count": grp.size(),
            "item_avg_price": grp["price"].mean(),
            "item_recency_days": (ref_date - grp["t_dat"].max()).dt.days,
        }
    )
    max_buyers = feats["item_unique_buyers"].max()
    feats["item_popularity_score"] = (
        feats["item_unique_buyers"] / max_buyers if max_buyers > 0 else 0.0
    )
    feats = feats[ITEM_FEATURE_COLS].astype("float32")
    feats.index = feats.index.astype("string")
    return feats


def build_user_features(train: pd.DataFrame) -> pd.DataFrame:
    """Compute user-level features from the training split.

    Mirrors dbt fct_user_features.  Channel ratio uses sales_channel_id where
    1 = online and 2 = in-store; user_online_ratio is the share of online rows.

    Returns
    -------
    DataFrame indexed by customer_id with USER_FEATURE_COLS (float32).
    """
    ref_date = train["t_dat"].max()
    grp = train.groupby("customer_id")
    span = grp["t_dat"].agg(["min", "max"])
    active_days = (span["max"] - span["min"]).dt.days
    recency_days = (ref_date - span["max"]).dt.days
    if "sales_channel_id" in train.columns:
        online = (train["sales_channel_id"] == 1).groupby(train["customer_id"]).mean()
    else:
        online = pd.Series(0.0, index=grp.size().index)
    feats = pd.DataFrame(
        {
            "user_purchase_count": grp.size(),
            "user_unique_items": grp["article_id"].nunique(),
            "user_total_spend": grp["price"].sum(),
            "user_avg_spend": grp["price"].mean(),
            "user_active_days": active_days,
            "user_recency_days": recency_days,
            "user_online_ratio": online,
        }
    )
    feats = feats[USER_FEATURE_COLS].astype("float32")
    feats.index = feats.index.astype("string")
    return feats


def user_seen_items(train: pd.DataFrame) -> dict[str, set[str]]:
    """Return {customer_id: set(article_id)} purchased during training."""
    return train.groupby("customer_id")["article_id"].apply(set).to_dict()


def assemble_feature_matrix(
    pairs: pd.DataFrame,
    item_features: pd.DataFrame,
    user_features: pd.DataFrame,
) -> pd.DataFrame:
    """Join (user, item) candidate pairs with user/item features.

    Parameters
    ----------
    pairs : DataFrame with customer_id, article_id, als_score, als_rank,
            ui_user_bought_item.
    item_features : output of build_item_features.
    user_features : output of build_user_features.

    Returns
    -------
    DataFrame with exactly FEATURE_COLS, float32, NaNs filled with 0.
    """
    df = pairs.merge(item_features, left_on="article_id", right_index=True, how="left")
    df = df.merge(user_features, left_on="customer_id", right_index=True, how="left")
    matrix = df[FEATURE_COLS].astype("float32").fillna(np.float32(0.0))
    return matrix
