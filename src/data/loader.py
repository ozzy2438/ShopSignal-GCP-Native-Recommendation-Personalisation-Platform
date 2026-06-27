"""
H&M dataset loader with resource-conscious MVP subset selection.

Design rationale
----------------
The full transactions_train.csv contains ~31 million rows (~3.5 GB).
Loading everything blindly would exceed typical laptop RAM and slow
every downstream iteration.  The MVP uses the LATEST N rows, which
corresponds to the most recent customer behaviour — the most useful
signal for a recency-sensitive recommender.

Subset strategy
---------------
  DEFAULT_SUBSET_ROWS = 2_000_000  (~200 MB when loaded)

  This is chosen to:
  - Keep peak RAM under ~1 GB including derived features
  - Cover enough unique users (~300-400 K) for meaningful ALS training
  - Remain well within BigQuery Sandbox free-tier limits when uploaded

  To change the subset size, set the SHOPSIGNAL_TX_ROWS environment
  variable or pass n_rows explicitly to load_transactions().

Download prerequisites
----------------------
  1. Create a Kaggle account at https://www.kaggle.com
  2. Go to Account → Settings → API → Create New API Token
     This downloads kaggle.json
  3. Place it at ~/.kaggle/kaggle.json and chmod 600 ~/.kaggle/kaggle.json
  4. pip install kaggle
  5. Run:
       kaggle competitions download \\
         -c h-and-m-personalized-fashion-recommendations \\
         --path data/raw/
       unzip data/raw/h-and-m-personalized-fashion-recommendations.zip \\
         -d data/raw/

  Expected files after extraction:
    data/raw/transactions_train.csv   (~3.5 GB, ~31 M rows)
    data/raw/articles.csv             (~54 MB,  105 K rows)
    data/raw/customers.csv            (~187 MB, 1.37 M rows)

  Raw files are excluded from Git — see .gitignore.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
DEFAULT_SUBSET_ROWS = int(os.getenv("SHOPSIGNAL_TX_ROWS", "2_000_000"))

TRANSACTIONS_FILE = RAW_DIR / "transactions_train.csv"
ARTICLES_FILE = RAW_DIR / "articles.csv"
CUSTOMERS_FILE = RAW_DIR / "customers.csv"

TRANSACTION_DTYPES = {
    "customer_id": "string",
    "article_id": "string",
    "price": "float32",
    "sales_channel_id": "int8",
}

ARTICLE_USE_COLS = [
    "article_id",
    "product_type_name",
    "product_group_name",
    "colour_group_name",
    "department_name",
    "detail_desc",
]

CUSTOMER_USE_COLS = [
    "customer_id",
    "age",
    "club_member_status",
    "fashion_news_frequency",
]


def _check_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required data file not found: {path}\n"
            "Run the Kaggle download steps documented in src/data/loader.py "
            "or docs/data.md before proceeding."
        )


def load_transactions(
    n_rows: int = DEFAULT_SUBSET_ROWS,
    raw_dir: Path = RAW_DIR,
) -> pd.DataFrame:
    """Load the latest n_rows transactions from transactions_train.csv.

    Reads only the tail of the file to stay within local memory limits.
    The file is sorted ascending by date, so the tail is the most recent
    behaviour — the most relevant signal for a recency-aware recommender.

    Parameters
    ----------
    n_rows:   Number of rows to load from the end of the file.
              Defaults to SHOPSIGNAL_TX_ROWS env var or 2_000_000.
    raw_dir:  Path to the directory containing the raw CSV files.
    """
    path = raw_dir / "transactions_train.csv"
    _check_file(path)

    with open(path) as fh:
        total = sum(1 for _ in fh) - 1  # minus header
    skip = max(0, total - n_rows)

    logger.info(
        "Loading transactions: total=%s, skip=%s, loading=%s",
        f"{total:,}",
        f"{skip:,}",
        f"{min(n_rows, total):,}",
    )

    skiprows = range(1, skip + 1) if skip > 0 else None
    df = pd.read_csv(
        path,
        skiprows=skiprows,
        dtype=TRANSACTION_DTYPES,
        parse_dates=["t_dat"],
    )
    df["t_dat"] = pd.to_datetime(df["t_dat"])
    df["article_id"] = df["article_id"].str.strip().str.zfill(10)
    df["customer_id"] = df["customer_id"].str.strip().str.lower()
    logger.info("Transactions loaded: shape=%s", df.shape)
    return df


def load_articles(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load all articles metadata."""
    path = raw_dir / "articles.csv"
    _check_file(path)
    df = pd.read_csv(path, usecols=ARTICLE_USE_COLS, dtype={"article_id": "string"})
    df["article_id"] = df["article_id"].str.strip().str.zfill(10)
    logger.info("Articles loaded: shape=%s", df.shape)
    return df


def load_customers(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Load all customers metadata."""
    path = raw_dir / "customers.csv"
    _check_file(path)
    df = pd.read_csv(path, usecols=CUSTOMER_USE_COLS, dtype={"customer_id": "string"})
    df["customer_id"] = df["customer_id"].str.strip().str.lower()
    logger.info("Customers loaded: shape=%s", df.shape)
    return df
