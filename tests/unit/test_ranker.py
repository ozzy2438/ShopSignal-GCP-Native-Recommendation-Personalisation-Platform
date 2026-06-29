"""Unit tests for src/models/ranker.py and the two-stage pipeline."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.features.build_features import FEATURE_COLS
from src.models.ranker import LightGBMRanker


def _toy_xy(n_users: int = 20, per_user: int = 6, seed: int = 0):
    rng = np.random.default_rng(seed)
    rows, y, group = [], [], []
    for _ in range(n_users):
        for r in range(per_user):
            als_score = per_user - r
            label = 1 if r == 0 else 0  # top als candidate is the positive
            feat = [als_score + rng.normal(0, 0.01) for _ in FEATURE_COLS]
            rows.append(feat)
            y.append(label)
        group.append(per_user)
    X = pd.DataFrame(rows, columns=FEATURE_COLS).astype("float32")
    return X, np.array(y), group


def test_fit_predict_shapes():
    X, y, group = _toy_xy()
    r = LightGBMRanker(n_estimators=20).fit(X, y, group)
    preds = r.predict(X)
    assert len(preds) == len(X)
    assert r.feature_cols == FEATURE_COLS


def test_group_mismatch_raises():
    X, y, _ = _toy_xy()
    with pytest.raises(ValueError, match="group sizes"):
        LightGBMRanker(n_estimators=5).fit(X, y, [3])


def test_rank_sorts_by_score():
    X, y, group = _toy_xy()
    r = LightGBMRanker(n_estimators=30).fit(X, y, group)
    cands = ["c0", "c1", "c2", "c3", "c4", "c5"]
    block = X.iloc[:6].copy()
    ranked = r.rank(cands, block)
    scores = r.predict(block)
    expected = [cands[i] for i in np.argsort(-scores, kind="stable")]
    assert ranked == expected


def test_predict_unfitted_raises():
    with pytest.raises(RuntimeError, match="not fitted"):
        LightGBMRanker().predict(pd.DataFrame({c: [0.0] for c in FEATURE_COLS}))


def test_save_load_roundtrip():
    X, y, group = _toy_xy()
    r = LightGBMRanker(n_estimators=20).fit(X, y, group)
    before = r.predict(X)
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "ranker.joblib"
        r.save(p)
        r2 = LightGBMRanker.load(p)
    np.testing.assert_allclose(before, r2.predict(X))
    assert r2.feature_cols == FEATURE_COLS


def test_empty_candidates_returns_empty():
    X, y, group = _toy_xy()
    r = LightGBMRanker(n_estimators=5).fit(X, y, group)
    assert r.rank([], X.iloc[:0]) == []
