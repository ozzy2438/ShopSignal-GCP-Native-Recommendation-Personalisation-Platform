"""Unit tests for model persistence and batch serving helpers."""

from __future__ import annotations

import pandas as pd

from src.features.ranking_dataset import build_ranking_dataset
from src.models.candidate_gen import ALSCandidateGenerator
from src.models.popularity import PopularityRecommender
from src.models.ranker import LightGBMRanker
from src.models.two_stage import TwoStageRecommender


def _tx() -> pd.DataFrame:
    rows = []
    for u in range(10):
        for i in range(6):
            rows.append(
                {
                    "customer_id": f"u{u}",
                    "article_id": f"a{(u + i) % 8}",
                    "price": 1.0 + i * 0.1,
                    "t_dat": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                    "sales_channel_id": 1,
                }
            )
    return pd.DataFrame(rows)


def test_popularity_save_load_roundtrip(tmp_path):
    pop = PopularityRecommender().fit(_tx())
    expected = pop.recommend("u1", k=5)
    pop.save(tmp_path / "pop.joblib")
    loaded = PopularityRecommender.load(tmp_path / "pop.joblib")
    assert loaded.recommend("u1", k=5) == expected
    assert loaded.n_articles == pop.n_articles


def _two_stage(tx):
    als = ALSCandidateGenerator(factors=8, iterations=3).fit(tx)
    pop = PopularityRecommender().fit(tx)
    cands = {f"u{i}": als.recommend(f"u{i}", k=15) for i in range(10)}
    labels = {u: set(c[:2]) for u, c in cands.items() if c}
    ds = build_ranking_dataset(cands, tx, labels, max_negatives=8, seed=1)
    ranker = LightGBMRanker(n_estimators=15).fit(ds.X, ds.y, ds.group)
    two = TwoStageRecommender(als, ranker, pop, n_candidates=15)
    two.fit_features(tx)
    return two


def test_two_stage_save_load_consistency(tmp_path):
    tx = _tx()
    two = _two_stage(tx)
    before = two.recommend("u1", k=5)
    two.save(tmp_path / "bundle")
    loaded = TwoStageRecommender.load(tmp_path / "bundle")
    assert loaded.recommend("u1", k=5) == before
    assert loaded.is_known_user("u1") is True
    assert loaded.is_known_user("ghost") is False


def test_batch_matches_individual(tmp_path):
    two = _two_stage(_tx())
    batch = two.recommend_batch(["u1", "u2", "ghost"], k=5)
    assert set(batch) == {"u1", "u2", "ghost"}
    assert batch["u1"] == two.recommend("u1", k=5)
    assert len(batch["ghost"]) == 5
