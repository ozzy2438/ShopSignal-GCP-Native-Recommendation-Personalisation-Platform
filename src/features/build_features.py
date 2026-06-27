"""
Feature engineering — build user and item feature matrices.

TODO(feat/data-pipeline):
  - Query fct_user_features and fct_item_features from BigQuery
  - Join with ALS candidate list
  - Encode categorical features
  - Return numpy / pandas feature matrix ready for LightGBM

Current state: placeholder interface only.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def build_user_features(customer_ids: list[str]) -> None:
    """Retrieve and encode user-level features from BigQuery.

    TODO: connect to BigQuery using google-cloud-bigquery,
    query shopsignal.fct_user_features, encode categoricals.
    """
    logger.warning("build_user_features() is a placeholder — returning None.")
    return None


def build_item_features(article_ids: list[str]) -> None:
    """Retrieve and encode item-level features from BigQuery.

    TODO: connect to BigQuery, query shopsignal.fct_item_features,
    one-hot encode product_type_name, colour_group_name, department_name.
    """
    logger.warning("build_item_features() is a placeholder — returning None.")
    return None
