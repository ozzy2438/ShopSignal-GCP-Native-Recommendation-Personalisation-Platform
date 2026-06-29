"""
Ranking dataset construction for the LightGBM ranker.

Builds the (user, candidate-item) training table that LGBMRanker consumes:

    row    = one user × one ALS candidate item
    label  = 1 if the user purchased that item in the LABEL window, else 0
    group  = number of candidates for the user (query size)
    feats  = item + user + ALS features (see build_features.FEATURE_COLS)

Timing / leakage contract
-------------------------
  * ALS is trained on TRAIN only and produces candidates per user.
  * features are computed from TRAIN only.
  * labels come from the LABEL split (val for selection, test for final eval).
This keeps every feature strictly "before the label period".

Sampling
--------
  * positives = candidates the user actually bought in the label window.
  * negatives = remaining candidates, capped at `max_negatives` per user with
    a deterministic seed for reproducibility.
  * users with no positive candidate are dropped from TRAINING (nothing to
    learn to rank) but kept for evaluation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features.build_features import (
    FEATURE_COLS,
    assemble_feature_matrix,
    build_item_features,
    build_user_features,
    user_seen_items,
)

logger = logging.getLogger(__name__)


@dataclass
class RankingDataset:
    """Feature matrix, labels, and per-user group sizes for LGBMRanker."""

    X: pd.DataFrame
    y: np.ndarray
    group: list[int]
    users: list[str]
    feature_cols: list[str]


def build_candidate_pairs(
    candidates: dict[str, list[str]],
    seen: dict[str, set[str]],
) -> pd.DataFrame:
    """Flatten {user: [items]} into rows with als_rank/score and seen flag."""
    records: list[dict] = []
    for user, items in candidates.items():
        user_seen = seen.get(user, set())
        n = len(items)
        for rank, item in enumerate(items):
            records.append(
                {
                    "customer_id": user,
                    "article_id": item,
                    "als_rank": rank,
                    "als_score": float(n - rank),  # higher = better; monotone in rank
                    "ui_user_bought_item": 1.0 if item in user_seen else 0.0,
                }
            )
    return pd.DataFrame.from_records(records)


def build_ranking_dataset(
    candidates: dict[str, list[str]],
    train: pd.DataFrame,
    labels: dict[str, set[str]],
    max_negatives: int = 50,
    seed: int = 42,
) -> RankingDataset:
    """Assemble a leakage-safe ranking dataset from ALS candidates.

    Parameters
    ----------
    candidates : {user: ordered candidate article_ids} from ALS (train only).
    train      : training transactions (features computed from here only).
    labels     : {user: set(purchased article_ids)} from the label window.
    max_negatives : cap on negative candidates per user (deterministic sample).
    seed       : RNG seed for reproducible negative sampling.

    Only users with >=1 positive candidate are included; group sizes are the
    per-user row counts, ordered to match X.
    """
    item_feats = build_item_features(train)
    user_feats = build_user_features(train)
    seen = user_seen_items(train)
    pairs = build_candidate_pairs(candidates, seen)
    if pairs.empty:
        return RankingDataset(pairs, np.array([], dtype=int), [], [], FEATURE_COLS)

    rng = np.random.default_rng(seed)
    keep_rows: list[pd.DataFrame] = []
    users: list[str] = []
    group: list[int] = []

    for user in sorted(candidates.keys()):
        relevant = labels.get(user, set())
        if not relevant:
            continue
        sub = pairs[pairs["customer_id"] == user]
        pos = sub[sub["article_id"].isin(relevant)]
        if pos.empty:
            continue
        neg = sub[~sub["article_id"].isin(relevant)]
        if len(neg) > max_negatives:
            neg = neg.iloc[rng.permutation(len(neg))[:max_negatives]]
        block = pd.concat([pos, neg]).sort_values("als_rank")
        keep_rows.append(block)
        users.append(user)
        group.append(len(block))

    if not keep_rows:
        return RankingDataset(pairs.iloc[0:0], np.array([], dtype=int), [], [], FEATURE_COLS)

    full = pd.concat(keep_rows, ignore_index=True)
    y = np.array(
        [1 if r.article_id in labels.get(r.customer_id, set()) else 0 for r in full.itertuples()],
        dtype=int,
    )
    X = assemble_feature_matrix(full, item_feats, user_feats)  # noqa: N806
    return RankingDataset(X=X, y=y, group=group, users=users, feature_cols=FEATURE_COLS)
