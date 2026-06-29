"""
Pipeline-level re-ranking: ALS top-200 → LightGBM re-rank → top-10.

Builds per-user candidate features (no labels) and applies a fitted
LightGBMRanker to produce ordered top-K recommendations.  Cold-start users
(no ALS factor) fall back to the popularity top-K, matching production
serving behaviour.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.features.build_features import (
    assemble_feature_matrix,
    build_item_features,
    build_user_features,
    user_seen_items,
)
from src.features.ranking_dataset import build_candidate_pairs

logger = logging.getLogger(__name__)


class TwoStageRecommender:
    """ALS candidate generation + LightGBM re-rank with popularity fallback."""

    def __init__(self, als, ranker, popularity, n_candidates: int = 200):
        self.als = als
        self.ranker = ranker
        self.popularity = popularity
        self.n_candidates = n_candidates
        self._item_feats: pd.DataFrame | None = None
        self._user_feats: pd.DataFrame | None = None
        self._seen: dict[str, set[str]] = {}

    def fit_features(self, train: pd.DataFrame) -> None:
        """Cache train-only feature tables used at re-rank time."""
        self._item_feats = build_item_features(train)
        self._user_feats = build_user_features(train)
        self._seen = user_seen_items(train)

    def recommend(self, user_id: str, k: int = 10, exclude_seen: bool = True) -> list[str]:
        try:
            cands = self.als.recommend(user_id, k=self.n_candidates, exclude_seen=exclude_seen)
        except KeyError:
            return self.popularity.recommend(user_id, k=k, exclude_seen=exclude_seen)
        if not cands:
            return self.popularity.recommend(user_id, k=k, exclude_seen=exclude_seen)
        pairs = build_candidate_pairs({user_id: cands}, self._seen)
        feats = assemble_feature_matrix(pairs, self._item_feats, self._user_feats)
        ranked = self.ranker.rank(cands, feats)
        return ranked[:k]
