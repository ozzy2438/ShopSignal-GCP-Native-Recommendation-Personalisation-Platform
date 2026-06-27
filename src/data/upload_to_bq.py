"""
BigQuery data upload utilities.

TODO(feat/data-pipeline):
  - Read H&M CSV files (last 2M rows of transactions)
  - Upload to BigQuery tables:
      shopsignal.raw_transactions
      shopsignal.raw_articles
      shopsignal.raw_customers
  - Validate row counts after load

Current state: placeholder interface only.
Requires GCP_PROJECT_ID and application-default credentials.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def upload_dataframe(df, table_id: str, project_id: str) -> None:  # noqa: ANN001
    """Upload a pandas DataFrame to a BigQuery table.

    TODO: implement using google.cloud.bigquery.Client.load_table_from_dataframe()
    with write_disposition=WRITE_TRUNCATE.
    """
    logger.warning(
        "upload_dataframe() is a placeholder — no data was uploaded. table_id=%s rows=%s",
        table_id,
        len(df) if df is not None else "N/A",
    )
