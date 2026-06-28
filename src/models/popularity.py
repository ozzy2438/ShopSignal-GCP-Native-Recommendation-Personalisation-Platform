"""
Popularity-based recommendation baseline.

Design
------
The popularity recommender ranks every article by its total purchase count
in the TRAINING split only.  It is a leakage-safe, zero-parameter model
that establishes the minimum bar any collaborative-filtering or ranking
model must beat before being promoted to production.

For known users the recommender can optionally exclude items the user has
already purchased in training (exclude_seen=True, the default), which
prevents trivial repeat-purchase recommendations from inflating recall.

For cold-start users (no training history) the recommender simply returns
the global top-K list — this is the production fallback behaviour.

Usage
-----
    from src.data.loader import load_transactions
    from src.data.split import make_temporal_split
    from src.models.popularity import PopularityRecommender

    tx    = load_transactions()
    split = make_temporal_split(tx)

    model = PopularityRecommender()
    model.fit(split.train)
    recs = model.recommend("some_customer_id", k=10)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PopularityRecommender:
    """Rank articles by training-set purchase frequency."""

    _counts: pd.Series = field(default_factory=pd.Series, repr=False)
    _top_k_cache: dict[int, list[str]] = field(default_factory=dict, repr=False)
    _user_seen: dict[str, set[str]] = field(default_factory=dict, repr=False)
    _fitted: bool = field(default=False, repr=False)

    def fit(self, train: pd.DataFrame) -> PopularityRecommender:
        """Compute article purchase counts from the training split.

        Parameters
        ----------
        train : Training transactions DataFrame with 'article_id' and
                'customer_id' columns.
        """
        if train.empty:
            raise ValueError("Training DataFrame is empty — cannot fit popularity model.")
        if "article_id" not in train.columns:
            raise ValueError("Training DataFrame must contain 'article_id'.")

        self._counts = (
            train.groupby("article_id")["article_id"]
            .count()
            .rename("purchase_count")
            .sort_values(ascending=False)
        )

        if "customer_id" in train.columns:
            self._user_seen = train.groupby("customer_id")["article_id"].apply(set).to_dict()

        self._top_k_cache = {}
        self._fitted = True

        logger.info(
            "PopularityRecommender fitted: %d unique articles, top article has %d purchases",
            len(self._counts),
            int(self._counts.iloc[0]),
        )
        return self

    def top_k(self, k: int = 10) -> list[str]:
        """Return the global top-K article IDs by purchase count."""
        self._check_fitted()
        if k not in self._top_k_cache:
            self._top_k_cache[k] = self._counts.index[:k].tolist()
        return self._top_k_cache[k]

    def recommend(
        self,
        user_id: str,
        k: int = 10,
        exclude_seen: bool = True,
    ) -> list[str]:
        """Return top-K recommendations for a user.

        Parameters
        ----------
        user_id      : Customer identifier.  If not seen in training,
                       the global top-K list is returned (cold-start fallback).
        k            : Number of recommendations.
        exclude_seen : If True, articles the user purchased in training are
                       removed before selecting top-K.
        """
        self._check_fitted()

        seen = self._user_seen.get(user_id, set()) if exclude_seen else set()

        if not seen:
            return self.top_k(k)

        recs: list[str] = []
        for article_id in self._counts.index:
            if article_id not in seen:
                recs.append(article_id)
            if len(recs) == k:
                break
        return recs

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("Model has not been fitted. Call .fit(train_df) first.")

    @property
    def n_articles(self) -> int:
        self._check_fitted()
        return len(self._counts)
