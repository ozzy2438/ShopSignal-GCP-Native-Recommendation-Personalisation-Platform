"""
ALS-based candidate generation — Stage 1 of the two-stage pipeline.

Design
------
Uses implicit.als.AlternatingLeastSquares trained on purchase count data
from the training split only.  The model produces top-200 candidate
article IDs per user, which Stage 2 (LightGBM ranker) then re-ranks
to top-10 using richer features.

Confidence weighting follows Hu et al. (2008):
    c_ui = 1 + alpha * r_ui
where r_ui is the raw purchase count for user u on item i, and alpha
controls how strongly repeated purchases increase confidence.

User/item index maps
--------------------
scipy sparse matrices work on integer indices, not string IDs.  The
mappings (user_id → row, article_id → col) are built from training data
and saved alongside the model so that recommendations can be decoded back
to article_id strings.

Cold-start handling
-------------------
Users not seen in training have no ALS latent factor.  recommend() raises
KeyError for unknown users so the caller can apply a popularity fallback
(see PopularityRecommender).  The pipeline layer should catch KeyError and
substitute fallback recommendations.

Persistence
-----------
save() / load() use joblib to serialise the fitted model, the sparse
matrix, and the string-to-index maps in a single file.  The file is
excluded from Git via .gitignore (models/*.joblib).

Usage
-----
    from src.data.loader import load_transactions
    from src.data.split import make_temporal_split
    from src.models.candidate_gen import ALSCandidateGenerator

    tx    = load_transactions()                    # 2M dev preset
    split = make_temporal_split(tx)

    gen   = ALSCandidateGenerator(factors=64, iterations=20)
    gen.fit(split.train)

    # known user
    candidates = gen.recommend("some_customer_id", k=200)

    # persist
    gen.save("models/als_model.joblib")
    gen2 = ALSCandidateGenerator.load("models/als_model.joblib")
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from implicit.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix

logger = logging.getLogger(__name__)

_DEFAULT_FACTORS = int(os.getenv("SHOPSIGNAL_ALS_FACTORS", "64"))
_DEFAULT_ITERATIONS = int(os.getenv("SHOPSIGNAL_ALS_ITERATIONS", "20"))
_DEFAULT_REGULARIZATION = float(os.getenv("SHOPSIGNAL_ALS_REGULARIZATION", "0.01"))
_DEFAULT_ALPHA = float(os.getenv("SHOPSIGNAL_ALS_ALPHA", "40.0"))


def build_user_item_matrix(
    train: pd.DataFrame,
    user_index: dict[str, int],
    item_index: dict[str, int],
    alpha: float = _DEFAULT_ALPHA,
) -> csr_matrix:
    """Build a confidence-weighted sparse user-item matrix from training rows.

    Parameters
    ----------
    train      : Training transactions with 'customer_id' and 'article_id'.
    user_index : {customer_id: row_index} mapping built from train.
    item_index : {article_id: col_index} mapping built from train.
    alpha      : Confidence scaling factor.  c_ui = 1 + alpha * count.

    Returns
    -------
    scipy.sparse.csr_matrix of shape (n_users, n_items).
    """
    counts = train.groupby(["customer_id", "article_id"]).size().reset_index(name="count")
    rows = counts["customer_id"].map(user_index).values
    cols = counts["article_id"].map(item_index).values
    data = (1.0 + alpha * counts["count"].values).astype(np.float32)

    return csr_matrix(
        (data, (rows, cols)),
        shape=(len(user_index), len(item_index)),
        dtype=np.float32,
    )


@dataclass
class ALSCandidateGenerator:
    """Wrapper around implicit ALS for top-K candidate retrieval."""

    factors: int = _DEFAULT_FACTORS
    iterations: int = _DEFAULT_ITERATIONS
    regularization: float = _DEFAULT_REGULARIZATION
    alpha: float = _DEFAULT_ALPHA
    random_state: int = 42

    _model: AlternatingLeastSquares | None = field(default=None, repr=False)
    _user_index: dict[str, int] = field(default_factory=dict, repr=False)
    _item_index: dict[str, int] = field(default_factory=dict, repr=False)
    _item_reverse: dict[int, str] = field(default_factory=dict, repr=False)
    _user_item_matrix: csr_matrix | None = field(default=None, repr=False)
    _fitted: bool = field(default=False, repr=False)

    def fit(self, train: pd.DataFrame) -> ALSCandidateGenerator:
        """Build the user-item matrix and train ALS on the training split.

        Parameters
        ----------
        train : Training transactions DataFrame.  Must contain 'customer_id'
                and 'article_id' columns.  Uses training data only — no val
                or test rows must be passed here.
        """
        if train.empty:
            raise ValueError("Training DataFrame is empty — cannot fit ALS model.")
        for col in ("customer_id", "article_id"):
            if col not in train.columns:
                raise ValueError(f"Training DataFrame must contain '{col}'.")

        users = sorted(train["customer_id"].unique())
        items = sorted(train["article_id"].unique())
        self._user_index = {u: i for i, u in enumerate(users)}
        self._item_index = {a: i for i, a in enumerate(items)}
        self._item_reverse = {i: a for a, i in self._item_index.items()}

        logger.info(
            "Building user-item matrix: %d users × %d items (alpha=%.0f)",
            len(users),
            len(items),
            self.alpha,
        )
        self._user_item_matrix = build_user_item_matrix(
            train, self._user_index, self._item_index, self.alpha
        )

        self._model = AlternatingLeastSquares(
            factors=self.factors,
            iterations=self.iterations,
            regularization=self.regularization,
            random_state=self.random_state,
            use_gpu=False,
        )
        logger.info(
            "Training ALS: factors=%d  iterations=%d  reg=%.4f",
            self.factors,
            self.iterations,
            self.regularization,
        )
        self._model.fit(self._user_item_matrix)
        self._fitted = True
        logger.info("ALS training complete.")
        return self

    def recommend(
        self,
        user_id: str,
        k: int = 200,
        exclude_seen: bool = True,
    ) -> list[str]:
        """Return top-K candidate article IDs for a user.

        Parameters
        ----------
        user_id      : Customer ID string.  Raises KeyError if not in training
                       data — the caller should apply a popularity fallback.
        k            : Number of candidates to return.
        exclude_seen : If True, items the user purchased in training are
                       filtered out before selecting top-K.

        Raises
        ------
        KeyError  : user_id was not seen during training (cold-start).
        RuntimeError : model has not been fitted.
        """
        self._check_fitted()
        if user_id not in self._user_index:
            raise KeyError(f"Unknown user '{user_id}' — apply popularity fallback.")

        row = self._user_index[user_id]
        user_vec = self._user_item_matrix[row]

        # Cap to avoid implicit padding when N > available candidates.
        # Padding repeats existing indices with near-zero scores and
        # silently inflates the result list with duplicates.
        n_seen = int(user_vec.nnz) if exclude_seen else 0
        effective_n = min(k, self.n_items - n_seen)
        if effective_n <= 0:
            return []

        ids, _ = self._model.recommend(
            row,
            user_vec,
            N=effective_n,
            filter_already_liked_items=exclude_seen,
        )

        # Deduplicate (padding can still repeat indices near vocab boundary)
        # and remove seen items as a belt-and-suspenders safety check.
        seen_cols = set(user_vec.indices) if exclude_seen else set()
        result: list[str] = []
        emitted: set[int] = set()
        for idx in ids:
            if idx in emitted or idx in seen_cols:
                continue
            emitted.add(idx)
            result.append(self._item_reverse[idx])
        return result

    def save(self, path: str | Path) -> None:
        """Persist the fitted model and index maps to a single joblib file."""
        self._check_fitted()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "model": self._model,
            "user_index": self._user_index,
            "item_index": self._item_index,
            "item_reverse": self._item_reverse,
            "user_item_matrix": self._user_item_matrix,
            "alpha": self.alpha,
            "factors": self.factors,
            "iterations": self.iterations,
            "regularization": self.regularization,
            "random_state": self.random_state,
        }
        joblib.dump(payload, path, compress=3)
        logger.info("ALS model saved → %s", path)

    @classmethod
    def load(cls, path: str | Path) -> ALSCandidateGenerator:
        """Load a previously saved ALSCandidateGenerator from disk."""
        data = joblib.load(path)
        obj = cls(
            factors=data["factors"],
            iterations=data["iterations"],
            regularization=data["regularization"],
            alpha=data["alpha"],
            random_state=data["random_state"],
        )
        obj._model = data["model"]
        obj._user_index = data["user_index"]
        obj._item_index = data["item_index"]
        obj._item_reverse = data["item_reverse"]
        obj._user_item_matrix = data["user_item_matrix"]
        obj._fitted = True
        return obj

    @property
    def n_users(self) -> int:
        self._check_fitted()
        return len(self._user_index)

    @property
    def n_items(self) -> int:
        self._check_fitted()
        return len(self._item_index)

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("Model has not been fitted. Call .fit(train_df) first.")
