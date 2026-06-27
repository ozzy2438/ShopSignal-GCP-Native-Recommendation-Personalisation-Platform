"""
Retraining pipeline entry point.

GitHub Actions MLOps workflow calls this script weekly (or on demand).

Planned stages
--------------
1. Data validation    — check BigQuery table freshness and row counts
2. Feature build      — materialise user/item features from dbt marts
3. ALS training       — fit collaborative filtering model
4. LightGBM training  — fit ranker on ALS candidates + features
5. Evaluation         — compute NDCG@10 on held-out validation set
6. Promotion gate     — compare NDCG against NDCG_PROMOTION_THRESHOLD
7. Artifact export    — save models, upload to GCS / MLflow registry
8. Deploy trigger     — if gate passes, trigger CD workflow

Current state: stub with mock metrics for CI demonstration.
TODO markers indicate where real logic will be inserted.
"""

from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NDCG_PROMOTION_THRESHOLD = float(os.getenv("NDCG_PROMOTION_THRESHOLD", "0.35"))


def validate_data() -> bool:
    """TODO: query BigQuery, assert table freshness (<24h), check row counts."""
    logger.info("[Stage 1/6] Data validation — PLACEHOLDER (returning True)")
    return True


def build_features() -> object:
    """TODO: call src/features/build_features.py against BigQuery dbt marts."""
    logger.info("[Stage 2/6] Feature building — PLACEHOLDER")
    return None


def train_als(features) -> object:  # noqa: ANN001
    """TODO: fit implicit.als.AlternatingLeastSquares on user-item matrix."""
    logger.info("[Stage 3/6] ALS candidate generation — PLACEHOLDER")
    return None


def train_ranker(als_model, features) -> object:  # noqa: ANN001
    """TODO: fit lightgbm.LGBMRanker with lambdarank objective."""
    logger.info("[Stage 4/6] LightGBM ranker training — PLACEHOLDER")
    return None


def evaluate(ranker, features) -> float:  # noqa: ANN001
    """TODO: compute NDCG@10 on held-out validation users."""
    logger.info("[Stage 5/6] Evaluation — PLACEHOLDER (returning mock NDCG=0.41)")
    return 0.41  # mock value — replace with real metric


def export_artifacts(als_model, ranker, ndcg: float) -> None:
    """TODO: save models with joblib, upload to GCS, register in MLflow."""
    logger.info("[Stage 6/6] Artifact export — PLACEHOLDER (ndcg=%.4f)", ndcg)


def main() -> None:
    logger.info("═══ ShopSignal Retrain Pipeline — START ═══")
    logger.warning("⚠️  Running in PLACEHOLDER mode — no real models are trained.")

    if not validate_data():
        logger.error("Data validation failed — aborting retrain.")
        sys.exit(1)

    features = build_features()
    als_model = train_als(features)
    ranker = train_ranker(als_model, features)
    ndcg = evaluate(ranker, features)

    logger.info("Candidate NDCG@10 = %.4f (threshold = %.4f)", ndcg, NDCG_PROMOTION_THRESHOLD)

    if ndcg >= NDCG_PROMOTION_THRESHOLD:
        logger.info("✅ Promotion gate PASSED — candidate model approved.")
        export_artifacts(als_model, ranker, ndcg)
    else:
        logger.error(
            "❌ Promotion gate FAILED (%.4f < %.4f) — deployment blocked.",
            ndcg,
            NDCG_PROMOTION_THRESHOLD,
        )
        sys.exit(1)

    logger.info("═══ ShopSignal Retrain Pipeline — DONE ═══")


if __name__ == "__main__":
    main()
