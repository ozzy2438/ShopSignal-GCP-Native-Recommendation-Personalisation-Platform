"""Unit tests for src/data/validate.py — no external files required."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data.validate import validate_articles, validate_customers, validate_transactions

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def valid_tx() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "t_dat": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
            "customer_id": ["cust_a", "cust_b", "cust_a"],
            "article_id": ["0123456789", "0987654321", "0123456789"],
            "price": [0.05, 0.10, 0.03],
            "sales_channel_id": [1, 2, 1],
        }
    )


@pytest.fixture()
def valid_articles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "article_id": ["0123456789", "0987654321"],
            "product_type_name": ["Trousers", "T-shirt"],
            "product_group_name": ["Garment Lower body", "Garment Upper body"],
            "colour_group_name": ["Black", "White"],
            "department_name": ["Mens Bottoms", "Mens Tops"],
        }
    )


@pytest.fixture()
def valid_customers() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["cust_a", "cust_b"],
        }
    )


# ── Transaction validation ────────────────────────────────────────────────────


class TestValidateTransactions:
    def test_clean_data_passes(self, valid_tx):
        report = validate_transactions(valid_tx)
        assert not report.has_errors

    def test_missing_column_is_error(self, valid_tx):
        report = validate_transactions(valid_tx.drop(columns=["customer_id"]))
        assert report.has_errors
        assert any("missing required columns" in e for e in report.errors)

    def test_null_customer_id_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "customer_id"] = None
        report = validate_transactions(df)
        assert report.has_errors
        assert any("null customer_id" in e for e in report.errors)

    def test_null_article_id_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "article_id"] = None
        report = validate_transactions(df)
        assert report.has_errors
        assert any("null article_id" in e for e in report.errors)

    def test_non_datetime_t_dat_is_error(self, valid_tx):
        df = valid_tx.copy()
        df["t_dat"] = df["t_dat"].astype(str)
        report = validate_transactions(df)
        assert report.has_errors
        assert any("t_dat" in e for e in report.errors)

    def test_invalid_sales_channel_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "sales_channel_id"] = 99
        report = validate_transactions(df)
        assert report.has_errors
        assert any("sales_channel_id" in e for e in report.errors)

    def test_zero_price_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "price"] = 0.0
        report = validate_transactions(df)
        assert report.has_errors
        assert any("price" in e for e in report.errors)

    def test_negative_price_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "price"] = -1.0
        report = validate_transactions(df)
        assert report.has_errors

    def test_null_price_is_error(self, valid_tx):
        df = valid_tx.copy()
        df.loc[0, "price"] = None
        report = validate_transactions(df)
        assert report.has_errors

    def test_stats_populated(self, valid_tx):
        report = validate_transactions(valid_tx)
        assert "row_count" in report.stats
        assert report.stats["row_count"] == 3
        assert report.stats["unique_customers"] == 2
        assert report.stats["unique_articles"] == 2

    def test_duplicate_rows_are_warnings_not_errors(self, valid_tx):
        df = pd.concat([valid_tx, valid_tx.iloc[[0]]], ignore_index=True)
        report = validate_transactions(df)
        assert not report.has_errors
        assert any("duplicate" in w.lower() for w in report.warnings)

    def test_date_range_stats(self, valid_tx):
        report = validate_transactions(valid_tx)
        assert report.stats["date_min"] == "2020-01-01"
        assert report.stats["date_max"] == "2020-03-01"


# ── Article validation ─────────────────────────────────────────────────────────


class TestValidateArticles:
    def test_clean_data_passes(self, valid_articles):
        report = validate_articles(valid_articles)
        assert not report.has_errors

    def test_missing_column_is_error(self, valid_articles):
        report = validate_articles(valid_articles.drop(columns=["article_id"]))
        assert report.has_errors

    def test_null_article_id_is_error(self, valid_articles):
        df = valid_articles.copy()
        df.loc[0, "article_id"] = None
        report = validate_articles(df)
        assert report.has_errors

    def test_duplicate_article_id_is_error(self, valid_articles):
        df = pd.concat([valid_articles, valid_articles.iloc[[0]]], ignore_index=True)
        report = validate_articles(df)
        assert report.has_errors
        assert any("duplicate article_id" in e for e in report.errors)


# ── Customer validation ────────────────────────────────────────────────────────


class TestValidateCustomers:
    def test_clean_data_passes(self, valid_customers):
        report = validate_customers(valid_customers)
        assert not report.has_errors

    def test_null_customer_id_is_error(self, valid_customers):
        df = valid_customers.copy()
        df.loc[0, "customer_id"] = None
        report = validate_customers(df)
        assert report.has_errors

    def test_duplicate_customer_id_is_error(self, valid_customers):
        df = pd.concat([valid_customers, valid_customers.iloc[[0]]], ignore_index=True)
        report = validate_customers(df)
        assert report.has_errors
        assert any("duplicate customer_id" in e for e in report.errors)
