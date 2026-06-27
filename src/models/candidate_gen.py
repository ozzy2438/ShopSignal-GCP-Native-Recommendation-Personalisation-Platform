"""
Candidate generation — ALS collaborative filtering.

TODO(feat/two-stage-model):
  - Load user-item interaction matrix from BigQuery
    (shopsignal.fct_user_item_interactions)
  - Train implicit.als.AlternatingLeastSquares
  - Retrieve top-200 candidates per user
  - Persist model with joblib to models/als_model.pkl
  - Upload artifact to GCS / MLflow

Current state: placeholder interface only.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ALSCandidateGenerator:
    """Thin wrapper around implicit ALS for candidate retrieval."""

    def __init__(self, factors: int = 64, iterations: int = 15, regularization: float = 0.01):
        self.factors = factors
        self.iterations = iterations
        self.regularization = regularization
        self._model = None  # TODO: replace with implicit.als.AlternatingLeastSquares

    def fit(self, user_item_matrix) -> None:  # noqa: ANN001
        """Train the ALS model.

        TODO: accept a scipy sparse matrix built from BigQuery interaction data.
        """
        logger.warning("ALSCandidateGenerator.fit() is a placeholder — no training performed.")

    def recommend(self, user_id: int, n_candidates: int = 200) -> list[str]:
        """Return top-N candidate article IDs for a given user.

        TODO: call self._model.recommend() with the trained matrix.
        """
        logger.warning("ALSCandidateGenerator.recommend() returning empty list (placeholder).")
        return []
