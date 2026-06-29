"""
Evidence run for the two-stage ALS → LightGBM ranker.

Trains ALS on a development sample, builds a leakage-safe ranking dataset
(features from train, labels from val), trains LGBMRanker with early stopping
on val, then evaluates ALS-only vs popularity vs re-ranked top-10 on the
held-out TEST split exactly once.  Prints metrics and peak RAM.

Run:
    OPENBLAS_NUM_THREADS=1 SHOPSIGNAL_TX_ROWS=1000000 python scripts/train_ranker.py
"""

from __future__ import annotations

import json
import logging
import os
import random
import resource
import time
from pathlib import Path

import numpy as np

from src.data.loader import load_transactions
from src.data.split import make_temporal_split
from src.evaluate.metrics import map_at_k, ndcg_at_k, recall_at_k
from src.features.ranking_dataset import build_ranking_dataset
from src.models.candidate_gen import ALSCandidateGenerator
from src.models.popularity import PopularityRecommender
from src.models.ranker import LightGBMRanker
from src.models.two_stage import TwoStageRecommender

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("evidence")
SEED = 42
K = 10
N_CAND = 200
MAX_TRAIN_USERS = int(os.getenv("RANK_TRAIN_USERS", "8000"))
MAX_TEST_USERS = int(os.getenv("RANK_TEST_USERS", "5000"))


def _avg(rec_fn, gt, users):
    n = nd = re = mp = 0
    for u in users:
        r = gt.get(u)
        if not r:
            continue
        recs = rec_fn(u)
        nd += ndcg_at_k(recs, r, K)
        re += recall_at_k(recs, r, K)
        mp += map_at_k(recs, r, K)
        n += 1
    return nd / n, re / n, mp / n, n


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    t0 = time.time()
    tx = load_transactions()
    split = make_temporal_split(tx)
    train_users = set(split.train.customer_id.unique())

    als = ALSCandidateGenerator(factors=64, iterations=40).fit(split.train)
    pop = PopularityRecommender().fit(split.train)

    val_gt = split.ground_truth("val")
    val_known = [u for u in val_gt if u in train_users]
    random.shuffle(val_known)
    val_known = val_known[:MAX_TRAIN_USERS]
    cand = {u: als.recommend(u, k=N_CAND) for u in val_known}
    ds = build_ranking_dataset(cand, split.train, val_gt, max_negatives=50, seed=SEED)
    log.info("dataset rows=%d groups=%d pos=%d", len(ds.X), len(ds.group), int(ds.y.sum()))

    cut = int(len(ds.group) * 0.85)
    tr = sum(ds.group[:cut])
    ranker = LightGBMRanker(n_estimators=300).fit(
        ds.X.iloc[:tr],
        ds.y[:tr],
        ds.group[:cut],
        eval_set=(ds.X.iloc[tr:], ds.y[tr:]),
        eval_group=ds.group[cut:],
    )
    two = TwoStageRecommender(als, ranker, pop, n_candidates=N_CAND)
    two.fit_features(split.train)

    test_gt = split.ground_truth("test")
    known = [u for u in test_gt if u in train_users]
    random.shuffle(known)
    known = known[:MAX_TEST_USERS]
    print(f"\nTEST known users={len(known)}")
    for name, fn in [
        ("popularity", lambda u: pop.recommend(u, k=K)),
        ("als_raw", lambda u: als.recommend(u, k=K)),
        ("two_stage", lambda u: two.recommend(u, k=K)),
    ]:
        nd, re, mp, n = _avg(fn, test_gt, known)
        print(f"  {name:11s} NDCG@10={nd:.4f} Recall@10={re:.4f} MAP@10={mp:.4f} n={n}")

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    print(
        f"\nruntime={time.time()-t0:.0f}s peakRAM~{rss:.1f}GB rows={os.getenv('SHOPSIGNAL_TX_ROWS')}"
    )

    out = Path("models")
    ranker.save(out / "lgbm_ranker.joblib")
    (out / "ranker_schema.json").write_text(json.dumps({"feature_cols": ds.feature_cols}, indent=2))
    (out / "ranker_meta.json").write_text(
        json.dumps(
            {
                "n_candidates": N_CAND,
                "max_negatives": 50,
                "seed": SEED,
                "k": K,
                "rows": tx.shape[0],
            },
            indent=2,
        )
    )
    print(f"artifacts → {out}/ (gitignored)")


if __name__ == "__main__":
    main()
