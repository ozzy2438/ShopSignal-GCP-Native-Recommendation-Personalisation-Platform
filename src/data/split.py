"""
Leakage-safe temporal train / validation / test split for H&M transactions.

Why temporal, not random?
--------------------------
A recommendation model trained on future data and evaluated on past data
will see artificially inflated metrics.  Any random split contaminates the
training set with purchases that happened AFTER the test period.

The correct approach mirrors real deployment: the model sees all purchases
up to a cut-off date and is asked to predict what happens after that date.

Split design
------------
                  |<——————— train ————————>|<— val —>|<— test —>|
  2018-09-20                           VAL_START   TEST_START   2020-09-22

  TRAIN_END   = VAL_START  - 1 day
  VAL_END     = TEST_START - 1 day

  Defaults (based on observed H&M data range 2018-09-20 → 2020-09-22,
  ~104 weeks total):

  VAL_START  = 2020-07-01   (last ~12 weeks for validation)
  TEST_START = 2020-08-12   (last ~6 weeks for test)

  These defaults can be overridden via environment variables:
    SHOPSIGNAL_VAL_START   e.g. "2020-07-01"
    SHOPSIGNAL_TEST_START  e.g. "2020-08-12"

Label creation
--------------
  Ground truth for a user in the val or test period = the set of article_ids
  they purchased during that period.  These are used as positive labels when
  computing NDCG@10, Recall@10, MAP@10.

  Articles a user bought during training are their "seen" items.  When
  evaluating, we compare predicted items against val/test ground truth.
  We do NOT exclude seen items from the prediction list during evaluation
  (the model should learn to down-rank them; excluding distorts metrics).
  This is documented here so the decision is explicit.

Cold-start treatment
--------------------
  Cold-start users (users in val/test not seen in train):
    - Excluded from metric computation (they cannot be evaluated fairly).
    - Counted and reported for transparency.
    - The serving layer handles them via a popularity fallback.

  Cold-start items (items in val/test not seen in train):
    - Included in ground truth.
    - ALS cannot retrieve them (they have no latent factor).
    - This naturally suppresses ALS recall on new items.
    - LightGBM can partially compensate via item-feature generalisation
      once item features are available.

  Minimum interaction threshold:
    - No minimum applied at split time.
    - Filtering (e.g. users with < 5 train interactions) is applied
      inside the ALS training stage, not here, so it is explicit and
      separately tested.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

_DEFAULT_VAL_START = "2020-07-01"
_DEFAULT_TEST_START = "2020-08-12"


def _get_cutoff(env_var: str, default: str) -> pd.Timestamp:
    return pd.Timestamp(os.getenv(env_var, default))


@dataclass
class TemporalSplit:
    """Container for the three split DataFrames and their metadata."""

    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    val_start: pd.Timestamp
    test_start: pd.Timestamp

    @property
    def train_end(self) -> pd.Timestamp:
        return self.val_start - pd.Timedelta(days=1)

    def summary(self) -> str:
        return (
            f"TemporalSplit:\n"
            f"  train : {len(self.train):>10,} rows  "
            f"[{self.train['t_dat'].min().date()} → {self.train_end.date()}]\n"
            f"  val   : {len(self.val):>10,} rows  "
            f"[{self.val_start.date()} → {(self.test_start - pd.Timedelta(days=1)).date()}]\n"
            f"  test  : {len(self.test):>10,} rows  "
            f"[{self.test_start.date()} → {self.test['t_dat'].max().date()}]\n"
            f"  train unique users : {self.train['customer_id'].nunique():,}\n"
            f"  val   unique users : {self.val['customer_id'].nunique():,}\n"
            f"  test  unique users : {self.test['customer_id'].nunique():,}\n"
            f"  cold-start val  users : {self._cold_start_count(self.val):,}\n"
            f"  cold-start test users : {self._cold_start_count(self.test):,}"
        )

    def _cold_start_count(self, df: pd.DataFrame) -> int:
        train_users = set(self.train["customer_id"].unique())
        return int((~df["customer_id"].isin(train_users)).any())

    def ground_truth(self, split: str = "test") -> dict[str, set[str]]:
        """Return {customer_id: set_of_purchased_article_ids} for val or test."""
        df = self.val if split == "val" else self.test
        return df.groupby("customer_id")["article_id"].apply(set).to_dict()

    def cold_start_users(self, split: str = "test") -> set[str]:
        """Return user IDs in val/test that have no training history."""
        train_users = set(self.train["customer_id"].unique())
        df = self.val if split == "val" else self.test
        return set(df["customer_id"].unique()) - train_users


def make_temporal_split(
    df: pd.DataFrame,
    val_start: str | None = None,
    test_start: str | None = None,
) -> TemporalSplit:
    """Split transactions into train / validation / test by date.

    Parameters
    ----------
    df         : Transactions DataFrame with a datetime 't_dat' column.
    val_start  : First date of the validation period (inclusive).
                 Defaults to SHOPSIGNAL_VAL_START env var or 2020-07-01.
    test_start : First date of the test period (inclusive).
                 Defaults to SHOPSIGNAL_TEST_START env var or 2020-08-12.

    Returns
    -------
    TemporalSplit dataclass with .train, .val, .test DataFrames.

    Raises
    ------
    ValueError if val_start >= test_start or if df is empty.
    """
    if df.empty:
        raise ValueError("Cannot split an empty DataFrame.")

    if not pd.api.types.is_datetime64_any_dtype(df["t_dat"]):
        raise ValueError("Column 't_dat' must be datetime before splitting.")

    ts_val = (
        pd.Timestamp(val_start)
        if val_start
        else _get_cutoff("SHOPSIGNAL_VAL_START", _DEFAULT_VAL_START)
    )
    ts_test = (
        pd.Timestamp(test_start)
        if test_start
        else _get_cutoff("SHOPSIGNAL_TEST_START", _DEFAULT_TEST_START)
    )

    if ts_val >= ts_test:
        raise ValueError(
            f"val_start ({ts_val.date()}) must be before test_start ({ts_test.date()})"
        )

    train = df[df["t_dat"] < ts_val].copy()
    val = df[(df["t_dat"] >= ts_val) & (df["t_dat"] < ts_test)].copy()
    test = df[df["t_dat"] >= ts_test].copy()

    if len(train) == 0:
        raise ValueError(f"Training split is empty — all data is on or after {ts_val.date()}")

    split = TemporalSplit(train=train, val=val, test=test, val_start=ts_val, test_start=ts_test)
    logger.info("%s", split.summary())
    return split
