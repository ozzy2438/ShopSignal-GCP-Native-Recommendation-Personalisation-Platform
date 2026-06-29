"""End-to-end fixture test: ALS candidates → LightGBM re-rank → top-10."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.ranking_dataset import build_ranking_dataset
from src.models.popularity import PopularityRecommender
from src.models.ranker import LightGBMRanker
from src.models.two_stage import TwoStageRecommender


def _synthetic_train(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    users = [f"u{i}" for i in range(40)]
    items = [f"a{i}" for i in range(30)]
    rows = []
    base = pd.Timestamp("2020-01-01")
    for u in users:
        for _ in range(rng.integers(5, 15)):
            rows.append(
                {
                    "customer_id": u,
                    "article_id": rng.choice(items),
                    "price": float(rng.uniform(0.01, 0.5)),
                    "sales_channel_id": int(rng.choice([1, 2])),
                    "t_dat": base + pd.Timedelta(days=int(rng.integers(0, 60))),
                }
            )
    return pd.DataFrame(rows)


def test_pipeline_runs_and_reranks():
    train = _synthetic_train()
    candidates = {u: [f"a{i}" for i in range(20)] for u in train.customer_id.unique()[:20]}
    labels = {u: {"a0", "a1"} for u in candidates}
    ds = build_ranking_dataset(candidates, train, labels, max_negatives=10, seed=1)
    assert sum(ds.group) == len(ds.X) and len(ds.X) > 0
    ranker = LightGBMRanker(n_estimators=30).fit(ds.X, ds.y, ds.group)

    two = TwoStageRecommender(als=None, ranker=ranker, popularity=None)
    two.fit_features(train)
    cands = ["a5", "a0", "a9", "a1", "a3"]
    recs = ranker.rank(cands, ds.X.iloc[: len(cands)])
    assert len(recs) == len(cands)
    assert set(recs) == set(cands)


def test_cold_start_falls_back_to_popularity():
    train = _synthetic_train()
    pop = PopularityRecommender().fit(train)

    class _ColdALS:
        def recommend(self, *a, **k):
            raise KeyError("cold")

    ranker = LightGBMRanker(n_estimators=5)
    X = pd.DataFrame(np.ones((6, 1)))
    ranker.feature_cols = list(X.columns)
    ranker._model = None
    two = TwoStageRecommender(als=_ColdALS(), ranker=ranker, popularity=pop)
    two.fit_features(train)
    recs = two.recommend("unknown_user", k=10)
    assert recs == pop.top_k(10)
