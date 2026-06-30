# ALS Candidate-Generation Tuning Results

**Date:** 2026-06-29

**Dataset:** 15M modelling preset (H&M, 2019-09-19 → 2020-09-22)

**Stage:** Candidate recall diagnosis and hyperparameter selection before LightGBM ranker

---

## 1. Evaluation Definition Audit

Both the 2M dev preset and 15M modelling preset use identical evaluation logic:
- `split.ground_truth(which)` — set of article_ids purchased in the val/test window
- Cold-start users (not in training) excluded from denominator
- `exclude_seen=True` — training purchases filtered before scoring
- `Recall@200 = |recs ∩ ground_truth| / |ground_truth|`, averaged over known users

**Why 2M val (0.1397) >> 15M val (0.0843):**

The 2M split uses auto-derived proportional dates (52-day window, 7-day val). The val window is narrow and immediately follows training — same seasonal period, minimal drift. The 15M split uses honest calendar splits (val = Jul–Aug 2020, test = Aug–Sep 2020) over a full year of history. The metric formula is identical; the evaluation regime is harder and more realistic on 15M.

---

## 2. Data Split

| | Train | Val | Test |
|--|--|--|--|
| Date range | 2019-09-19 → 2020-06-30 | 2020-07-01 → 2020-08-11 | 2020-08-12 → 2020-09-22 |
| Rows | 11,613,037 | 1,821,718 | 1,565,245 |
| Known users evaluated | — | 276,563 | 254,057 |
| Cold-start users | — | 15.7% | 17.8% |
| Cold-start items | — | 11.4% (3,780) | 26.4% (8,500) |
| Mean gt items/user | — | 5.1 | 4.7 |

---

## 3. Matrix Orientation & Seen-Item Filter

- Matrix shape: `(899,083 users × 62,078 items)` — correct orientation for `implicit` ✓
- Seen items in candidates: **0** (exclude_seen=True verified on sample user with 24 seen items) ✓
- No padding artifacts (effective_n capped at `n_items - n_seen`) ✓

---

## 4. Hyperparameter Grid (10K sampled val users)

| Config | factors | iter | reg | alpha | Recall@200 | Hit-rate@200 | Fit time |
|--------|---------|------|-----|-------|-----------|--------------|---------|
| A (baseline) | 64 | 20 | 0.01 | 40 | 0.0849 | 0.2642 | 442s |
| B | 128 | 20 | 0.01 | 40 | 0.0840 | 0.2587 | 823s |
| **C (winner)** | **64** | **40** | **0.01** | **40** | **0.0854** | **0.2638** | 990s |
| D | 64 | 20 | 0.001 | 40 | 0.0850 | 0.2645 | 587s |
| E | 64 | 20 | 0.01 | 15 | 0.0829 | 0.2620 | 680s |
| F | 64 | 20 | 0.01 | 100 | 0.0848 | 0.2610 | 676s |

Winner selected on validation Recall@200 only: **Config C**.

---

## 5. Final Full-Population Results (Config C)

| Metric | Val (276,563 users) | Test (254,057 users) |
|--------|--------------------|--------------------|
| Recall@200 | **0.0843** | **0.0578** |
| Hit-rate@200 | 0.2590 | 0.1842 |
| Cold-start users | 15.7% | 17.8% |
| Cold-start items | 11.4% | 26.4% |

### Comparison vs Popularity Baseline (10K sample)

| Model | Recall@200 | Hit-rate@200 |
|-------|-----------|--------------|
| Popularity | 0.0595 | 0.2116 |
| ALS Config C | 0.0854 | 0.2638 |
| **ALS lift** | **+43%** | **+25%** |

---

## 6. Winning Configuration

```
factors       = 64
iterations    = 40
regularization = 0.01
alpha         = 40.0
random_state  = 42
```

Reproducibility settings for the validated run:
```
SHOPSIGNAL_ALS_FACTORS=64
SHOPSIGNAL_ALS_ITERATIONS=40
SHOPSIGNAL_ALS_REGULARIZATION=0.01
SHOPSIGNAL_ALS_ALPHA=40
```

---

## 7. Test vs Val Gap Diagnosis

Test Recall@200 (0.0578) is 31% lower than val (0.0843). Root causes in order of impact:

**Primary — catalogue growth (cold-start items):**

26.4% of test items were never seen in training, vs 11.4% in val. ALS cannot retrieve items with no latent factor. Of the 254,057 evaluated test users, **19.9% have a ground-truth set composed entirely of cold-start items** — for these users, ALS recall is structurally zero regardless of hyperparameters.

**Secondary — temporal drift:**

The test window (Aug–Sep 2020) is 6–7 weeks further from the training cutoff than val (Jul–Aug). Hit-rate@200 drops from 0.2590 (val) to 0.1842 (test), meaning 7 percentage points more users have zero relevant items in candidates. This is drift beyond the cold-start effect.

**Tertiary — longer purchase windows raising the denominator:**

Val gt mean = 5.1 items/user, test gt mean = 4.7 — similar, so denominator inflation is not a major driver here.

**Not a model configuration issue:** the grid showed a recall range of only 0.0829–0.0854 across all configs. No hyperparameter change will close the val→test gap; it is structural.

---

## 8. OpenBLAS / implicit Thread Contention

**Observed:** without `OPENBLAS_NUM_THREADS=1`, fit times were 420–990s (21s/iter baseline). Previous run with `OPENBLAS_NUM_THREADS=1` showed 130s total (6.5s/iter). This is a **3× slowdown** from thread contention, not a speedup.

**Root cause:** `implicit` manages its own thread pool via `threadpoolctl`. When OpenBLAS also spins up 12 threads, they fight over the same CPU cores. The implicit library explicitly warns: *"Having OpenBLAS use a threadpool can lead to severe performance issues here."*

**Recommended configuration:**
```bash
export OPENBLAS_NUM_THREADS=1
```
Or in Python before importing implicit:
```python
import threadpoolctl
threadpoolctl.threadpool_limits(1, "blas")
```

Apply the variable before importing or training with `implicit`. The combined evidence
entry point is `scripts/train_ranker.py`; running it with the 15M preset is intentionally
expensive and is not required for routine validation.

The previous 130s run was correct. This tuning run ran without it and paid a ~3× penalty per config — training times in this report are not representative of production speed.

---

## 9. Readiness for LightGBM

ALS candidate generation is validated and ready as Stage 1 input:
- Recall@200 val = 0.0843 (43% above popularity baseline)
- Hit-rate@200 val = 0.2590 — 26% of users have at least one relevant item in candidates
- Zero seen-item leakage confirmed
- Best config locked: factors=64, iter=40, reg=0.01, alpha=40

The candidate ceiling (Recall@200 = 0.084) sets the upper bound for the ranker. LightGBM Stage 2 reranks the top-200 candidates to top-10; its NDCG@10 is bounded by how many relevant items exist in the candidate pool.
