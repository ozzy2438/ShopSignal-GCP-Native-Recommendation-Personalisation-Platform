"""Integration tests for the two-stage serving path using a tiny fixture bundle.

Builds a real ALS + LightGBM + popularity bundle from a handful of synthetic
transactions, saves it, points SHOPSIGNAL_MODEL_DIR at it, reloads the model
registry, and exercises the live FastAPI endpoints.  No full dataset or GCP.
"""

from __future__ import annotations

import importlib

import pandas as pd
import pytest

from src.features.ranking_dataset import build_ranking_dataset
from src.models.candidate_gen import ALSCandidateGenerator
from src.models.popularity import PopularityRecommender
from src.models.ranker import LightGBMRanker
from src.models.two_stage import TwoStageRecommender


def _toy_transactions() -> pd.DataFrame:
    rows = []
    for u in range(12):
        for i in range(8):
            rows.append(
                {
                    "customer_id": f"u{u}",
                    "article_id": f"a{(u + i) % 10}",
                    "price": 1.0 + i * 0.1,
                    "t_dat": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                    "sales_channel_id": 1 if i % 2 == 0 else 2,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def bundle_dir(tmp_path):
    tx = _toy_transactions()
    als = ALSCandidateGenerator(factors=8, iterations=3).fit(tx)
    pop = PopularityRecommender().fit(tx)
    cands = {u: als.recommend(u, k=20) for u in [f"u{i}" for i in range(12)]}
    labels = {u: set(c[:2]) for u, c in cands.items() if c}
    ds = build_ranking_dataset(cands, tx, labels, max_negatives=10, seed=1)
    ranker = LightGBMRanker(n_estimators=20).fit(ds.X, ds.y, ds.group)
    two = TwoStageRecommender(als, ranker, pop, n_candidates=20)
    two.fit_features(tx)
    out = tmp_path / "bundle"
    two.save(out)
    return out


@pytest.fixture
def client(bundle_dir, monkeypatch):
    monkeypatch.setenv("SHOPSIGNAL_MODEL_DIR", str(bundle_dir))
    import src.serve.app as app_mod
    import src.serve.model_registry as reg

    importlib.reload(reg)
    importlib.reload(app_mod)
    from fastapi.testclient import TestClient

    c = TestClient(app_mod.app)
    yield c
    monkeypatch.delenv("SHOPSIGNAL_MODEL_DIR", raising=False)
    importlib.reload(reg)
    importlib.reload(app_mod)


def test_version_reports_model_loaded(client):
    body = client.get("/version").json()
    assert body["model_loaded"] is True
    assert body["model_stage"] == "als+lgbm"
    assert len(body["feature_cols"]) > 0


def test_known_user_uses_two_stage(client):
    body = client.post("/recommend", json={"customer_id": "u1", "top_n": 5}).json()
    assert body["source"] == "als+lgbm"
    assert len(body["recommendations"]) <= 5
    scores = [r["score"] for r in body["recommendations"]]
    assert scores == sorted(scores, reverse=True)


def test_cold_start_falls_back_to_popularity(client):
    body = client.post("/recommend", json={"customer_id": "ghost", "top_n": 10}).json()
    assert body["source"] == "popularity"
    assert len(body["recommendations"]) == 10


def test_batch_returns_per_user_results(client):
    body = client.post(
        "/recommend/batch", json={"customer_ids": ["u1", "u2", "ghost"], "top_n": 5}
    ).json()
    assert len(body["results"]) == 3
    assert body["source"] == "als+lgbm"
    assert {r["customer_id"] for r in body["results"]} == {"u1", "u2", "ghost"}
