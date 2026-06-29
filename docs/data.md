# Data and Evaluation Guide

## Source dataset

ShopSignal uses the **H&M Personalized Fashion Recommendations** Kaggle dataset.

| File | Approximate source size | Purpose |
|---|---:|---|
| `transactions_train.csv` | 31 million rows / 3.5 GB | Implicit purchase events |
| `articles.csv` | 105,000 rows / 54 MB | Product attributes |
| `customers.csv` | 1.37 million rows / 187 MB | Customer attributes |

H&M is a useful public benchmark because it contains a realistic retail catalogue,
repeat purchase behaviour, continuous product introduction, and enough history to expose
temporal drift and cold-start limitations.

## Download and local placement

Accept the competition terms on Kaggle, install/configure its CLI, then run:

```bash
kaggle competitions download \
  -c h-and-m-personalized-fashion-recommendations \
  --path data/raw/

unzip data/raw/h-and-m-personalized-fashion-recommendations.zip \
  -d data/raw/
```

Expected files:

```text
data/raw/
├── articles.csv
├── customers.csv
└── transactions_train.csv
```

The raw files are not committed. They are large, this repository intentionally does not
redistribute the competition dataset, and Git is not an artifact store. Trained model
bundles are also omitted; serialized files below `models/` are gitignored.

## Local loading presets

`src/data/loader.py` reads the latest N rows from the chronologically ordered transaction
file. Set `SHOPSIGNAL_TX_ROWS` before loading:

| Preset | Rows | Observed date range | Intended use |
|---|---:|---|---|
| Development (default) | 2,000,000 | 2020-08-01 to 2020-09-22 | Fast local iteration |
| Modelling | 15,000,000 | 2019-09-19 to 2020-09-22 | Final evidence run |

```bash
export SHOPSIGNAL_TX_ROWS=15000000
export OPENBLAS_NUM_THREADS=1
```

The final reports use the modelling preset. Peak RAM for the complete two-stage
evaluation was approximately 6.3 GB; runtime was approximately 1 hour 56 minutes.
Do not rerun that job for ordinary development or documentation checks.

## Validation

The validators enforce schema and value constraints before modelling. Transaction checks
cover required IDs, dates, positive prices, and sales-channel values; article and customer
checks cover required identifiers and duplicates. Soft warnings retain potentially valid
repeat-purchase or date-range anomalies for inspection.

```bash
python - <<'PY'
from src.data.loader import load_articles, load_customers, load_transactions
from src.data.validate import validate_articles, validate_customers, validate_transactions

frames = (load_transactions(), load_articles(), load_customers())
validators = (validate_transactions, validate_articles, validate_customers)

for validate, frame in zip(validators, frames, strict=True):
    print(validate(frame).summary())
PY
```

The local CSV loader/validator path is implemented. `src/data/upload_to_bq.py` is an
interface stub, so this repository does not claim that the evidence dataset was uploaded
to BigQuery. The dbt directory provides BigQuery-oriented transformation models for a
future connected cloud path.

## Leakage-safe temporal split

Randomly splitting transactions would let a model learn from purchases that occur after
the interactions it is asked to predict. ShopSignal instead mirrors deployment by using
past interactions to predict later windows:

```text
train: 2019-09-19 ───────────── 2020-06-30
validation:                         2020-07-01 ── 2020-08-11
test:                                                2020-08-12 ── 2020-09-22
```

### Final modelling split

| Split | Rows | Purpose |
|---|---:|---|
| Train | 11,613,037 | Fit popularity, ALS, and train-only feature aggregates |
| Validation | 1,821,718 | ALS selection and ranker early stopping/model selection |
| Test | 1,565,245 | One final untouched model comparison |

The split rows total 15,000,000. The fitted ALS matrix contains 899,083 users and
62,078 items.

Leakage controls are enforced in code:

1. `make_temporal_split` creates non-overlapping date windows.
2. Popularity and ALS receive only `split.train`.
3. User and item ranking features are aggregated only from training rows.
4. Labels come from later ground-truth windows and are not inputs to the features.
5. Training purchases are excluded from ALS recommendations during evaluation.
6. The test window is not used for tuning.

For the 2M development preset, the default calendar cutoffs predate the loaded range.
`make_temporal_split` therefore derives proportional cutoffs at 75% and 87.5% of that
range. Those shorter-window metrics are not directly comparable with the final 15M run.

## Evaluation populations and cold start

Known-user metrics average over users who appear in training and have ground truth in the
evaluation window. New users have no ALS factor, so they are excluded from those offline
metrics and reported separately. At serving time they receive the popularity fallback.

New items remain in validation/test ground truth. This is deliberately strict: ALS cannot
retrieve an item with no training interaction, and excluding it would hide a real
catalogue-coverage problem.

| Diagnostic | Validation | Test |
|---|---:|---:|
| Known users evaluated for Recall@200 | 276,563 | 254,057 |
| Cold-start users | 15.7% | 17.8% |
| Cold-start items | 11.4% (3,780) | 26.4% (8,500) |

Test Recall@200 is lower than validation (0.0578 vs 0.0843) primarily because:

- H&M introduced substantially more test-period items that had no training factor;
- 19.9% of evaluated test users purchased only cold-start items, making ALS recall
  structurally zero for those users; and
- the test window is farther from the training cutoff, increasing temporal drift.

The similar validation/test ground-truth size per user means denominator growth is not
the main cause.

## Why compare popularity, ALS, and LightGBM?

- **Popularity** is the lowest-complexity, leakage-safe benchmark and the serving fallback.
- **ALS** tests whether collaborative implicit-feedback structure improves candidate
  retrieval beyond global frequency.
- **LightGBM LambdaMART** tests whether train-only behavioural features and ALS scores can
  improve top-10 ordering within the same candidate set.

This decomposition prevents a ranker result from concealing weak retrieval. Recall@200
measures the candidate ceiling; NDCG@10, Recall@10, and MAP@10 measure final ordering.

## OpenBLAS reproducibility

Use `OPENBLAS_NUM_THREADS=1` for ALS evidence runs. The `implicit` library manages its own
parallel work, and a second OpenBLAS thread pool caused oversubscription on the validation
machine. Observed tuning fits were roughly three times slower without the limit.

```bash
OPENBLAS_NUM_THREADS=1 SHOPSIGNAL_TX_ROWS=15000000 \
  python scripts/train_ranker.py
```

This command is documented for reproducibility, not as part of the routine test suite.
See `docs/als_tuning_results.md` and `docs/lightgbm_ranker_results.md` before considering
an expensive rerun.
