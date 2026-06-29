"""
Pipeline-level re-ranking: ALS top-200 → LightGBM re-rank → top-10.

Builds per-user candidate features (no labels) and applies a fitted
LightGBMRanker to produce ordered top-K recommendations.  Cold-start users
(no ALS factor) fall back to the popularity top-K, matching production
serving behaviour.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from src.features.build_features import (
    FEATURE_COLS,
    assemble_feature_matrix,
    build_item_features,
    build_user_features,
    user_seen_items,
)
from src.features.ranking_dataset import build_candidate_pairs
from src.models.candidate_gen import ALSCandidateGenerator
from src.models.popularity import PopularityRecommender
from src.models.ranker import LightGBMRanker

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

    def recommend_batch(
        self, user_ids: list[str], k: int = 10, exclude_seen: bool = True
    ) -> dict[str, list[str]]:
        """Re-rank top-K recommendations for a list of users (cold-start safe)."""
        return {u: self.recommend(u, k=k, exclude_seen=exclude_seen) for u in user_ids}

    def is_known_user(self, user_id: str) -> bool:
        """True when ALS has a latent factor for the user (not cold-start)."""
        return user_id in self.als._user_index

    def save(self, dir_path: str | Path) -> None:
        """Persist all components + feature tables + schema into a directory."""
        if self._item_feats is None or self._user_feats is None:
            raise RuntimeError("fit_features() must run before save().")
        out = Path(dir_path)
        out.mkdir(parents=True, exist_ok=True)
        self.als.save(out / "als_model.joblib")
        self.ranker.save(out / "lgbm_ranker.joblib")
        self.popularity.save(out / "popularity.joblib")
        joblib.dump(
            {"item": self._item_feats, "user": self._user_feats, "seen": self._seen},
            out / "features.joblib",
            compress=3,
        )
        (out / "feature_schema.json").write_text(
            json.dumps({"feature_cols": FEATURE_COLS}, indent=2)
        )
        (out / "two_stage_meta.json").write_text(
            json.dumps({"n_candidates": self.n_candidates, "feature_cols": FEATURE_COLS}, indent=2)
        )
        logger.info("TwoStageRecommender bundle saved → %s", out)

    @classmethod
    def load(cls, dir_path: str | Path) -> TwoStageRecommender:
        """Load a bundle previously written by save()."""
        d = Path(dir_path)
        als = ALSCandidateGenerator.load(d / "als_model.joblib")
        ranker = LightGBMRanker.load(d / "lgbm_ranker.joblib")
        pop = PopularityRecommender.load(d / "popularity.joblib")
        meta = json.loads((d / "two_stage_meta.json").read_text())
        obj = cls(als, ranker, pop, n_candidates=meta.get("n_candidates", 200))
        feats = joblib.load(d / "features.joblib")
        obj._item_feats = feats["item"]
        obj._user_feats = feats["user"]
        obj._seen = feats["seen"]
        return obj
