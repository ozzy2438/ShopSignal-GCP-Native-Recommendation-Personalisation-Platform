"""
Offline evaluator for recommendation models.

Separates known users (evaluable) from cold-start users (not evaluable)
and reports NDCG@K, Recall@K, MAP@K for each group.

Cold-start users are excluded from metric computation — they have no training
history so no model can fairly evaluate them.  Their count and rate are
reported for transparency.

Usage
-----
    from src.evaluate.evaluator import evaluate
    from src.models.popularity import PopularityRecommender

    model = PopularityRecommender().fit(split.train)
    report = evaluate(model, split, which="val", k=10)
    print(report.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.data.split import TemporalSplit
from src.evaluate.metrics import map_at_k, ndcg_at_k, recall_at_k

logger = logging.getLogger(__name__)

K_DEFAULT = 10


@dataclass
class MetricSet:
    ndcg: float
    recall: float
    map: float
    n_users: int

    def __str__(self) -> str:
        return (
            f"NDCG@K={self.ndcg:.4f}  "
            f"Recall@K={self.recall:.4f}  "
            f"MAP@K={self.map:.4f}  "
            f"(n={self.n_users:,})"
        )


@dataclass
class EvalReport:
    known: MetricSet
    cold_start_n: int
    cold_start_rate: float
    split: str
    k: int

    def summary(self) -> str:
        return (
            f"EvalReport [{self.split}  K={self.k}]\n"
            f"  known users  : {self.known}\n"
            f"  cold-start   : {self.cold_start_n:,} users excluded "
            f"({self.cold_start_rate:.1%} of {self.split} users)"
        )


def evaluate(
    model: object,
    split: TemporalSplit,
    which: str = "val",
    k: int = K_DEFAULT,
    exclude_seen: bool = True,
) -> EvalReport:
    """Evaluate a fitted recommender on the val or test split.

    Parameters
    ----------
    model        : Any fitted recommender with a .recommend(user_id, k, exclude_seen)
                   method that returns a list of article_id strings.
    split        : TemporalSplit produced by make_temporal_split.
    which        : 'val' or 'test'.
    k            : Evaluation cut-off rank.
    exclude_seen : Passed to model.recommend — exclude training-seen items.

    Returns
    -------
    EvalReport with per-group metrics.
    """
    if which not in ("val", "test"):
        raise ValueError(f"which must be 'val' or 'test', got {which!r}")

    ground_truth = split.ground_truth(which)
    cold_start = split.cold_start_users(which)

    eval_df = split.val if which == "val" else split.test
    total_users = eval_df["customer_id"].nunique()

    ndcg_scores: list[float] = []
    recall_scores: list[float] = []
    map_scores: list[float] = []

    for user_id, relevant in ground_truth.items():
        if user_id in cold_start:
            continue
        if not relevant:
            continue

        recs = model.recommend(user_id, k=k, exclude_seen=exclude_seen)
        ndcg_scores.append(ndcg_at_k(recs, relevant, k))
        recall_scores.append(recall_at_k(recs, relevant, k))
        map_scores.append(map_at_k(recs, relevant, k))

    n_evaluated = len(ndcg_scores)
    n_cold = len(cold_start)

    if n_evaluated == 0:
        logger.warning("No users were evaluated — all are cold-start or have empty ground truth.")
        known = MetricSet(ndcg=0.0, recall=0.0, map=0.0, n_users=0)
    else:
        known = MetricSet(
            ndcg=sum(ndcg_scores) / n_evaluated,
            recall=sum(recall_scores) / n_evaluated,
            map=sum(map_scores) / n_evaluated,
            n_users=n_evaluated,
        )

    logger.info("evaluate(%s): evaluated=%d  cold-start=%d", which, n_evaluated, n_cold)

    return EvalReport(
        known=known,
        cold_start_n=n_cold,
        cold_start_rate=n_cold / total_users if total_users > 0 else 0.0,
        split=which,
        k=k,
    )
