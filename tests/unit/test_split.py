"""Unit tests for src/data/split.py — no external files required."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.split import TemporalSplit, make_temporal_split

# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def tx_fixture() -> pd.DataFrame:
    """Small transaction fixture spanning Jan–Sep 2020."""
    dates = [
        "2020-01-10",
        "2020-01-15",
        "2020-02-20",  # → train
        "2020-07-05",
        "2020-07-12",  # → val
        "2020-08-15",
        "2020-08-20",
        "2020-09-01",  # → test
    ]
    return pd.DataFrame(
        {
            "t_dat": pd.to_datetime(dates),
            "customer_id": ["u1", "u2", "u1", "u1", "u3", "u2", "u1", "u4"],
            "article_id": ["a1", "a2", "a3", "a1", "a2", "a3", "a4", "a1"],
            "price": [0.05] * 8,
            "sales_channel_id": [1] * 8,
        }
    )


# ── Core split logic ──────────────────────────────────────────────────────────


class TestMakeTemporalSplit:
    VAL_START = "2020-07-01"
    TEST_START = "2020-08-12"

    def test_returns_temporal_split(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert isinstance(s, TemporalSplit)

    def test_train_rows_before_val_start(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert (s.train["t_dat"] < pd.Timestamp(self.VAL_START)).all()

    def test_val_rows_in_correct_window(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert (s.val["t_dat"] >= pd.Timestamp(self.VAL_START)).all()
        assert (s.val["t_dat"] < pd.Timestamp(self.TEST_START)).all()

    def test_test_rows_on_or_after_test_start(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert (s.test["t_dat"] >= pd.Timestamp(self.TEST_START)).all()

    def test_no_data_leakage(self, tx_fixture):
        """Training data must not contain any dates >= val_start."""
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert s.train["t_dat"].max() < pd.Timestamp(self.VAL_START)

    def test_no_overlap_between_splits(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        train_dates = set(s.train["t_dat"].dt.date)
        val_dates = set(s.val["t_dat"].dt.date)
        test_dates = set(s.test["t_dat"].dt.date)
        assert train_dates.isdisjoint(val_dates)
        assert train_dates.isdisjoint(test_dates)
        assert val_dates.isdisjoint(test_dates)

    def test_total_rows_preserved(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert len(s.train) + len(s.val) + len(s.test) == len(tx_fixture)

    def test_val_start_before_test_start_required(self, tx_fixture):
        with pytest.raises(ValueError, match="before test_start"):
            make_temporal_split(tx_fixture, "2020-09-01", "2020-07-01")

    def test_empty_dataframe_raises(self):
        empty = pd.DataFrame(
            columns=["t_dat", "customer_id", "article_id", "price", "sales_channel_id"]
        )
        with pytest.raises(ValueError, match="empty"):
            make_temporal_split(empty, self.VAL_START, self.TEST_START)

    def test_non_datetime_column_raises(self, tx_fixture):
        df = tx_fixture.copy()
        df["t_dat"] = df["t_dat"].astype(str)
        with pytest.raises(ValueError, match="datetime"):
            make_temporal_split(df, self.VAL_START, self.TEST_START)

    def test_train_end_property(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert s.train_end == pd.Timestamp(self.VAL_START) - pd.Timedelta(days=1)


# ── Ground truth and cold-start ───────────────────────────────────────────────


class TestGroundTruth:
    VAL_START = "2020-07-01"
    TEST_START = "2020-08-12"

    def test_ground_truth_returns_dict_of_sets(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        gt = s.ground_truth("test")
        assert isinstance(gt, dict)
        for v in gt.values():
            assert isinstance(v, set)

    def test_ground_truth_only_contains_test_period_items(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        gt = s.ground_truth("test")
        test_users = set(s.test["customer_id"].unique())
        assert set(gt.keys()).issubset(test_users)

    def test_cold_start_users_not_in_train(self, tx_fixture):
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        train_users = set(s.train["customer_id"].unique())
        cold = s.cold_start_users("test")
        assert cold.isdisjoint(train_users)

    def test_u4_is_cold_start_in_test(self, tx_fixture):
        """u4 only appears in test — should be identified as cold-start."""
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert "u4" in s.cold_start_users("test")

    def test_u3_is_cold_start_in_val(self, tx_fixture):
        """u3 only appears in val — should be identified as cold-start in val."""
        s = make_temporal_split(tx_fixture, self.VAL_START, self.TEST_START)
        assert "u3" in s.cold_start_users("val")


# ── Summary string ────────────────────────────────────────────────────────────


class TestSummary:
    def test_summary_contains_row_counts(self, tx_fixture):
        s = make_temporal_split(tx_fixture, "2020-07-01", "2020-08-12")
        summary = s.summary()
        assert "train" in summary
        assert "val" in summary
        assert "test" in summary
        assert "cold-start" in summary
