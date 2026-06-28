"""Unit tests for src/evaluate/evaluator.py — no external files required."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.split import make_temporal_split
from src.evaluate.evaluator import EvalReport, MetricSet, evaluate
from src.models.popularity import PopularityRecommender


@pytest.fixture()
def split_fixture():
    """Fixture with 4 users over 3 periods and known ground truth."""
    dates = [
        "2020-01-01",
        "2020-01-05",
        "2020-01-10",  # train (3 rows)
        "2020-07-01",
        "2020-07-02",  # val  (2 rows, u1 and u2)
        "2020-08-15",
        "2020-08-20",  # test (2 rows, u1 and u3-new)
    ]
    df = pd.DataFrame(
        {
            "t_dat": pd.to_datetime(dates),
            "customer_id": ["u1", "u2", "u1", "u1", "u2", "u1", "u4"],
            "article_id": ["a1", "a2", "a3", "a2", "a1", "a1", "a5"],
            "price": [0.05] * 7,
            "sales_channel_id": [1] * 7,
        }
    )
    return make_temporal_split(df, val_start="2020-07-01", test_start="2020-08-12")


@pytest.fixture()
def fitted_model(split_fixture):
    return PopularityRecommender().fit(split_fixture.train)


class TestEvaluate:
    def test_returns_eval_report(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val", k=10)
        assert isinstance(report, EvalReport)

    def test_split_field(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val")
        assert report.split == "val"

    def test_k_field(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val", k=5)
        assert report.k == 5

    def test_known_is_metric_set(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val")
        assert isinstance(report.known, MetricSet)

    def test_metrics_in_range(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val", k=10)
        for metric in (report.known.ndcg, report.known.recall, report.known.map):
            assert 0.0 <= metric <= 1.0

    def test_cold_start_users_excluded_from_n_users(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="test", k=10)
        # u4 is cold-start in test; only u1 is known → n_users = 1
        assert report.known.n_users == 1
        assert report.cold_start_n == 1

    def test_cold_start_rate_is_fraction(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="test", k=10)
        assert 0.0 <= report.cold_start_rate <= 1.0

    def test_invalid_which_raises(self, fitted_model, split_fixture):
        with pytest.raises(ValueError, match="which"):
            evaluate(fitted_model, split_fixture, which="train")

    def test_summary_contains_key_labels(self, fitted_model, split_fixture):
        report = evaluate(fitted_model, split_fixture, which="val", k=10)
        summary = report.summary()
        assert "EvalReport" in summary
        assert "known users" in summary
        assert "cold-start" in summary

    def test_val_all_known_users_evaluated(self, fitted_model, split_fixture):
        # val has u1 and u2, both in train
        report = evaluate(fitted_model, split_fixture, which="val", k=10)
        assert report.known.n_users == 2
        assert report.cold_start_n == 0
