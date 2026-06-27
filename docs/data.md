# Data Guide — ShopSignal

## Source dataset

**H&M Personalized Fashion Recommendations** (Kaggle competition dataset)

| File | Size | Rows | Description |
|------|------|------|-------------|
| `transactions_train.csv` | ~3.5 GB | ~31 million | Customer purchase events |
| `articles.csv` | ~54 MB | ~105,000 | Product metadata |
| `customers.csv` | ~187 MB | ~1.37 million | Customer attributes |

Why H&M?
- Real product names and descriptions (enables semantic search later)
- Production-scale volume
- Retail/fashion domain — closest public benchmark to eCommerce

## Download instructions

### Prerequisites

1. Create an account at [kaggle.com](https://www.kaggle.com)
2. Go to **Account → Settings → API → Create New API Token** — this downloads `kaggle.json`
3. Place and protect the file:

```bash
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json
```

4. Install the CLI:

```bash
pip install kaggle
```

### Download and extract

```bash
kaggle competitions download \
  -c h-and-m-personalized-fashion-recommendations \
  --path data/raw/

unzip data/raw/h-and-m-personalized-fashion-recommendations.zip \
  -d data/raw/
```

Expected result:

```
data/raw/
├── articles.csv
├── customers.csv
└── transactions_train.csv
```

### Why raw files are excluded from Git

`data/raw/` is listed in `.gitignore` because:

- `transactions_train.csv` is ~3.5 GB — far above GitHub's 100 MB per-file limit
- Committing data to Git creates a permanent copy in history that cannot be fully removed
- The Kaggle terms of service do not permit redistribution
- Re-downloading from Kaggle is reproducible and free

## MVP subset strategy

The full 31-million-row file cannot be loaded into laptop RAM efficiently and
would make every training iteration slow.

**Default strategy: use the latest 2 million transactions.**

The file is sorted ascending by date, so reading the tail gives the most recent
customer behaviour — the most relevant signal for a recency-sensitive recommender.

Approximate characteristics of the 2M-row subset:
- ~300–400 K unique customers
- ~90–100 K unique articles
- ~200 MB in memory
- Covers roughly the final 4–6 months of the dataset

### Changing the subset size

Set `SHOPSIGNAL_TX_ROWS` before running any pipeline step:

```bash
export SHOPSIGNAL_TX_ROWS=500000   # smaller — faster iteration
export SHOPSIGNAL_TX_ROWS=5000000  # larger — more coverage, more RAM
```

The default is `2_000_000`. This is documented in `src/data/loader.py`.

## Running validation

```bash
python -c "
from src.data.loader import load_transactions, load_articles, load_customers
from src.data.validate import validate_transactions, validate_articles, validate_customers

tx  = load_transactions()
art = load_articles()
cst = load_customers()

for fn, df in [(validate_transactions, tx), (validate_articles, art), (validate_customers, cst)]:
    report = fn(df)
    print(report.summary())
"
```

### What validation checks

**Transactions:**

| Check | Type | Reason |
|-------|------|--------|
| Required columns present | Hard | Pipeline cannot proceed without them |
| Null `customer_id` | Hard | Cannot build user-item matrix |
| Null `article_id` | Hard | Cannot build user-item matrix |
| `t_dat` is datetime | Hard | Split and recency features require dates |
| Null or invalid dates | Hard | Corrupted rows |
| `sales_channel_id` ∈ {1, 2} | Hard | Only store (1) and online (2) are valid |
| `price` > 0 and not null | Hard | Implicit feedback weighting uses price |
| Non-numeric `article_id` sample | Soft | Highlights ID format inconsistencies |
| Duplicate (customer, article, date) rows | Soft | These are legitimate repeat purchases, not errors |
| Date range outside expected window | Soft | Surfaced for awareness only |

**Articles:** required columns, no null or duplicate `article_id`.

**Customers:** required `customer_id`, no nulls or duplicates.

## Temporal split design

See `src/data/split.py` for full documentation. Summary:

```
|<——————————————— train ————————————————>|<——— val ———>|<——— test ———>|
2018-09-20                           2020-06-30   2020-07-01   2020-08-12   2020-09-22
```

| Split | Start | End | Purpose |
|-------|-------|-----|---------|
| train | 2018-09-20 | 2020-06-30 | ALS + LightGBM training |
| val | 2020-07-01 | 2020-08-11 | Hyperparameter tuning, early stopping |
| test | 2020-08-12 | 2020-09-22 | Final offline evaluation |

Dates are configurable via environment variables:

```bash
export SHOPSIGNAL_VAL_START=2020-07-01
export SHOPSIGNAL_TEST_START=2020-08-12
```

### Why this split prevents data leakage

1. Training data contains zero rows from the val or test period
2. Feature engineering (recency, purchase counts) is computed only on training rows
3. dbt mart queries will be parameterised to exclude val/test dates

### Cold-start handling

| Scenario | Treatment |
|----------|-----------|
| User in val/test, not in train | Excluded from metric computation; counted and reported |
| Item in val/test, not in train | Included in ground truth; ALS cannot retrieve it; reported as cold-start item recall gap |
| Serving | Popularity fallback for unknown users |
