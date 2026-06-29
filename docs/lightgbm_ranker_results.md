# LightGBM Re-Ranker — Full-Preset Evaluation

Second-stage LambdaMART ranker over ALS top-200 candidates → top-10. Evaluated on
the 15M H&M modelling preset using the validated ALS config (factors=64,
iterations=40, regularization=0.01, alpha=40, `OPENBLAS_NUM_THREADS=1`).

## Protocol

- Train: 11,613,037 rows (2019-09-19 → 2020-06-30)
- Val:   1,821,718 rows (2020-07-01 → 2020-08-11) — model selection + early stopping only
- Test:  1,565,245 rows (2020-08-12 → 2020-09-22) — evaluated once, never tuned
- Leakage-safe temporal split; features computed strictly before the label window.
- Ranking dataset: 270,134 rows, 5,244 user groups, 7,934 positive / 262,200 negative.
- best_iteration = 76; LGBMRanker lambdarank, val NDCG@10 = 0.289.

## Top-10 metrics (known users)

| Metric | popularity | raw ALS | two-stage |
|---|---|---|---|
| VAL NDCG@10 | 0.0056 | 0.0102 | **0.0136** |
| VAL Recall@10 | 0.0075 | 0.0128 | **0.0171** |
| VAL MAP@10 | 0.0025 | 0.0054 | **0.0067** |
| TEST NDCG@10 | 0.0065 | 0.0089 | **0.0094** |
| TEST Recall@10 | 0.0085 | 0.0110 | **0.0124** |
| TEST MAP@10 | 0.0031 | 0.0047 | 0.0046 |

Two-stage re-ranking beats raw ALS on validation (+33% NDCG@10) and on the
untouched test set (+6% NDCG@10, +12% Recall@10; MAP@10 at parity).

## Feature importance (gain)

item_avg_price, item_unique_buyers, item_purchase_count, als_score,
user_avg_spend, user_active_days, user_recency_days, user_total_spend,
user_online_ratio. `item_popularity_score` and `ui_user_bought_item` unused.

## Resources & limits

- Runtime ~6,934s (~1h56m); peak RAM ~6.3 GB.
- Cold-start val/test users ~15.7% / 17.8% fall back to popularity (no ALS history).
- Coverage limited by ALS candidate recall; not all val/test users had positives.
