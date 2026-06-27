"""
LightGBM LambdaMART ranker — Stage 2 of the two-stage pipeline.

TODO(feat/two-stage-model):
  - Build feature matrix from ALS candidates + fct_item_features + fct_user_features
  - Train with lightgbm.LGBMRanker(objective='lambdarank', metric='ndcg')
  - Evaluate with NDCG@10 on a held-out validation split
  - Persist with joblib to models/lgbm_ranker.pkl
  - Compare NDCG against promotion threshold before deploying

Current state: placeholder interface only.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LightGBMRanker:
    """Thin wrapper around LightGBM LambdaMART for list-wise ranking."""

    def __init__(self, n_estimators: int = 500, learning_rate: float = 0.05, num_leaves: int = 63):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self._model = None  # TODO: replace with lightgbm.LGBMRanker(...)

    def fit(self, X, y, group) -> None:  # noqa: ANN001, N803
        """Train the LambdaMART ranker.

        TODO: accept feature matrix X, binary relevance labels y,
        and group sizes (number of candidates per user).
        """
        logger.warning("LightGBMRanker.fit() is a placeholder — no training performed.")

    def rank(self, candidates: list[str], features) -> list[str]:  # noqa: ANN001
        """Re-rank candidate list by predicted relevance score.

        TODO: call self._model.predict(features) and sort candidates.
        """
        logger.warning("LightGBMRanker.rank() returning unranked candidates (placeholder).")
        return candidates
