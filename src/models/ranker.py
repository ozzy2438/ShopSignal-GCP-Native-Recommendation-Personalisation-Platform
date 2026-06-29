"""
LightGBM LambdaMART ranker — Stage 2 of the two-stage pipeline.

Re-ranks the top-200 ALS candidates per user down to top-10 using item, user
and ALS features.  Trained with the lambdarank objective and NDCG metric; the
group/query sizes are the number of candidates per user.

Persistence uses joblib (models/*.joblib are git-ignored).  The fitted feature
schema is stored with the model so predict() always sees columns in the exact
training order and dtype.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRanker, early_stopping, log_evaluation

logger = logging.getLogger(__name__)


class LightGBMRanker:
    """LambdaMART re-ranker over ALS candidates."""

    def __init__(
        self,
        n_estimators: int = 500,
        learning_rate: float = 0.05,
        num_leaves: int = 63,
        random_state: int = 42,
        n_jobs: int = 1,
    ):
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.num_leaves = num_leaves
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.feature_cols: list[str] | None = None
        self._model: LGBMRanker | None = None

    def fit(
        self,
        X: pd.DataFrame,  # noqa: N803
        y,  # noqa: ANN001
        group: list[int],
        eval_set: tuple | None = None,
        eval_group: list[int] | None = None,
        early_stopping_rounds: int | None = 50,
        ndcg_eval_at: tuple[int, ...] = (10,),
    ) -> LightGBMRanker:
        """Train the LambdaMART ranker on per-user candidate groups."""
        if sum(group) != len(X):
            raise ValueError(f"group sizes sum to {sum(group)} but X has {len(X)} rows")
        self.feature_cols = list(X.columns)
        self._model = LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            n_estimators=self.n_estimators,
            learning_rate=self.learning_rate,
            num_leaves=self.num_leaves,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            verbose=-1,
        )
        callbacks = []
        fit_kwargs: dict = {"group": group, "eval_at": ndcg_eval_at}
        if eval_set is not None and eval_group is not None:
            fit_kwargs["eval_set"] = [eval_set]
            fit_kwargs["eval_group"] = [eval_group]
            if early_stopping_rounds:
                callbacks = [early_stopping(early_stopping_rounds), log_evaluation(0)]
        self._model.fit(X, y, callbacks=callbacks, **fit_kwargs)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:  # noqa: N803
        """Predict relevance scores for a feature matrix."""
        self._check_fitted()
        return self._model.predict(X[self.feature_cols])

    def rank(self, candidates: list[str], features: pd.DataFrame) -> list[str]:
        """Return candidates sorted by descending predicted score."""
        if not candidates:
            return []
        scores = self.predict(features)
        order = np.argsort(-scores, kind="stable")
        return [candidates[i] for i in order]

    def save(self, path: str | Path) -> None:
        self._check_fitted()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "feature_cols": self.feature_cols}, path, compress=3)
        logger.info("LightGBM ranker saved → %s", path)

    @classmethod
    def load(cls, path: str | Path) -> LightGBMRanker:
        data = joblib.load(path)
        obj = cls()
        obj._model = data["model"]
        obj.feature_cols = data["feature_cols"]
        return obj

    def _check_fitted(self) -> None:
        if self._model is None:
            raise RuntimeError("Ranker is not fitted. Call .fit(X, y, group) first.")
