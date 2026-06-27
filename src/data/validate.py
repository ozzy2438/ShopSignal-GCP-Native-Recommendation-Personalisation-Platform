"""
Data validation for the H&M dataset.

All checks operate on plain pandas DataFrames so they can be called
against real data or small test fixtures without touching Kaggle or GCP.

Validation philosophy
---------------------
- HARD checks (raise DataValidationError) block the pipeline entirely.
  Used for structural problems (missing columns, all-null IDs, etc.)
  that make downstream modelling impossible.

- SOFT checks (log a warning, return the warning in the report) surface
  data quality concerns without stopping the pipeline.  The caller
  decides whether to promote the warning to a hard failure.

Usage
-----
    from src.data.validate import validate_transactions, validate_articles

    report = validate_transactions(df)
    if report.has_errors:
        raise SystemExit(report.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

VALID_SALES_CHANNELS = {1, 2}
MIN_DATE = pd.Timestamp("2018-01-01")
MAX_DATE = pd.Timestamp("2021-12-31")

REQUIRED_TX_COLUMNS = {"t_dat", "customer_id", "article_id", "price", "sales_channel_id"}
REQUIRED_ARTICLE_COLUMNS = {
    "article_id",
    "product_type_name",
    "product_group_name",
    "colour_group_name",
    "department_name",
}
REQUIRED_CUSTOMER_COLUMNS = {"customer_id"}


class DataValidationError(ValueError):
    """Raised when a hard validation check fails."""


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        lines = ["=== Validation Report ==="]
        lines += [f"  STAT    {k}: {v}" for k, v in self.stats.items()]
        lines += [f"  WARNING {w}" for w in self.warnings]
        lines += [f"  ERROR   {e}" for e in self.errors]
        status = "FAILED" if self.has_errors else "PASSED"
        lines.append(f"=== {status} ({len(self.errors)} errors, {len(self.warnings)} warnings) ===")
        return "\n".join(lines)


def _check_required_columns(df: pd.DataFrame, required: set[str], name: str) -> list[str]:
    missing = required - set(df.columns)
    if missing:
        return [f"{name}: missing required columns: {sorted(missing)}"]
    return []


def validate_transactions(df: pd.DataFrame) -> ValidationReport:
    """Run all validation checks on the transactions DataFrame.

    Parameters
    ----------
    df : DataFrame produced by load_transactions() or a compatible fixture.

    Returns
    -------
    ValidationReport with errors (hard failures) and warnings (soft issues).
    """
    report = ValidationReport()

    # ── Column presence ───────────────────────────────────────────────────────
    col_errors = _check_required_columns(df, REQUIRED_TX_COLUMNS, "transactions")
    if col_errors:
        report.errors.extend(col_errors)
        return report  # no point continuing without required columns

    n = len(df)
    report.stats["row_count"] = n

    # ── Null IDs (hard) ───────────────────────────────────────────────────────
    null_customers = df["customer_id"].isna().sum()
    null_articles = df["article_id"].isna().sum()
    if null_customers > 0:
        report.errors.append(f"transactions: {null_customers:,} null customer_id values")
    if null_articles > 0:
        report.errors.append(f"transactions: {null_articles:,} null article_id values")

    # ── Date validity (hard) ──────────────────────────────────────────────────
    if not pd.api.types.is_datetime64_any_dtype(df["t_dat"]):
        report.errors.append("transactions: t_dat is not datetime — call pd.to_datetime() first")
    else:
        null_dates = df["t_dat"].isna().sum()
        if null_dates > 0:
            report.errors.append(f"transactions: {null_dates:,} null dates in t_dat")

        out_of_range = df[(df["t_dat"] < MIN_DATE) | (df["t_dat"] > MAX_DATE)]
        if len(out_of_range) > 0:
            report.warnings.append(
                f"transactions: {len(out_of_range):,} rows outside expected date range "
                f"[{MIN_DATE.date()}, {MAX_DATE.date()}]"
            )

        report.stats["date_min"] = str(df["t_dat"].min().date())
        report.stats["date_max"] = str(df["t_dat"].max().date())

    # ── Sales channel validity (hard) ─────────────────────────────────────────
    invalid_channels = ~df["sales_channel_id"].isin(VALID_SALES_CHANNELS)
    if invalid_channels.any():
        bad_vals = df.loc[invalid_channels, "sales_channel_id"].unique().tolist()
        report.errors.append(
            f"transactions: invalid sales_channel_id values: {bad_vals} "
            f"(expected {sorted(VALID_SALES_CHANNELS)})"
        )

    # ── Price validity (hard) ─────────────────────────────────────────────────
    non_positive = (df["price"] <= 0).sum()
    null_price = df["price"].isna().sum()
    if null_price > 0:
        report.errors.append(f"transactions: {null_price:,} null price values")
    if non_positive > 0:
        report.errors.append(f"transactions: {non_positive:,} rows with price <= 0")

    # ── Article ID type consistency (soft) ────────────────────────────────────
    sample = df["article_id"].dropna().head(1000)
    non_numeric = sample[~sample.str.match(r"^\d+$", na=False)]
    if len(non_numeric) > 0:
        report.warnings.append(
            f"transactions: {len(non_numeric)} article_id values in sample are non-numeric"
        )

    # ── Cardinality stats (info) ──────────────────────────────────────────────
    report.stats["unique_customers"] = int(df["customer_id"].nunique())
    report.stats["unique_articles"] = int(df["article_id"].nunique())

    # ── Duplicate behaviour (soft) ────────────────────────────────────────────
    dupe_key = ["customer_id", "article_id", "t_dat"]
    n_dupes = df.duplicated(subset=dupe_key).sum()
    if n_dupes > 0:
        report.warnings.append(
            f"transactions: {n_dupes:,} duplicate (customer_id, article_id, t_dat) rows — "
            "these are legitimate repeat-purchase events, not data errors"
        )
        report.stats["duplicate_rows"] = int(n_dupes)

    _log_report(report, "transactions")
    return report


def validate_articles(df: pd.DataFrame) -> ValidationReport:
    """Validate the articles metadata DataFrame."""
    report = ValidationReport()

    col_errors = _check_required_columns(df, REQUIRED_ARTICLE_COLUMNS, "articles")
    if col_errors:
        report.errors.extend(col_errors)
        return report

    report.stats["row_count"] = len(df)

    null_ids = df["article_id"].isna().sum()
    if null_ids > 0:
        report.errors.append(f"articles: {null_ids:,} null article_id values")

    n_dupes = df.duplicated(subset=["article_id"]).sum()
    if n_dupes > 0:
        report.errors.append(f"articles: {n_dupes:,} duplicate article_id values")

    report.stats["unique_articles"] = int(df["article_id"].nunique())

    null_pct = df[list(REQUIRED_ARTICLE_COLUMNS - {"article_id"})].isna().mean()
    for col, pct in null_pct.items():
        if pct > 0.05:
            report.warnings.append(f"articles: column '{col}' has {pct:.1%} null values")

    _log_report(report, "articles")
    return report


def validate_customers(df: pd.DataFrame) -> ValidationReport:
    """Validate the customers metadata DataFrame."""
    report = ValidationReport()

    col_errors = _check_required_columns(df, REQUIRED_CUSTOMER_COLUMNS, "customers")
    if col_errors:
        report.errors.extend(col_errors)
        return report

    report.stats["row_count"] = len(df)

    null_ids = df["customer_id"].isna().sum()
    if null_ids > 0:
        report.errors.append(f"customers: {null_ids:,} null customer_id values")

    n_dupes = df.duplicated(subset=["customer_id"]).sum()
    if n_dupes > 0:
        report.errors.append(f"customers: {n_dupes:,} duplicate customer_id values")

    report.stats["unique_customers"] = int(df["customer_id"].nunique())

    _log_report(report, "customers")
    return report


def _log_report(report: ValidationReport, name: str) -> None:
    if report.has_errors:
        logger.error("Validation FAILED for %s:\n%s", name, report.summary())
    elif report.warnings:
        logger.warning("Validation passed with warnings for %s:\n%s", name, report.summary())
    else:
        logger.info("Validation PASSED for %s: %s", name, report.stats)
