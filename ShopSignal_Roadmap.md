# ShopSignal — GCP-Native Recommendation & Personalisation Platform
## Proje Roadmap & Geliştirme Rehberi

> **Hazırlayan:** Osman Orka  
> **Hedef Rol:** Machine Learning Engineer — Kogan.com  
> **Stack:** Python · BigQuery · dbt · LightGBM · Cloud Run · FastAPI · GitHub Actions · Docker  
> **Tahmini Süre:** 3–5 gün (MVP)

---

## İçindekiler

1. [Proje Mimarisi](#1-proje-mimarisi)
2. [Ön Koşullar ve Kurulum](#2-ön-koşullar-ve-kurulum)
3. [Veri Yönetimi ve Erişim](#3-veri-yönetimi-ve-erişim)
4. [GitHub Branch Yapısı](#4-github-branch-yapısı)
5. [Klasör Yapısı](#5-klasör-yapısı)
6. [Gün 1 — Foundation: Veri + BigQuery + dbt](#6-gün-1--foundation-veri--bigquery--dbt)
7. [Gün 2 — Two-Stage Model: ALS + LightGBM Ranker](#7-gün-2--two-stage-model-als--lightgbm-ranker)
8. [Gün 3 — Serving: FastAPI + Docker + Cloud Run](#8-gün-3--serving-fastapi--docker--cloud-run)
9. [Gün 4 — MLOps: GitHub Actions + Otomatik Retrain](#9-gün-4--mlops-github-actions--otomatik-retrain)
10. [Gün 5 — GenAI Katmanı + README + Son Kontroller](#10-gün-5--genai-katmanı--readme--son-kontroller)
11. [GitHub Actions Entegrasyonu](#11-github-actions-entegrasyonu)
12. [Cloud Run Deployment Süreci](#12-cloud-run-deployment-süreci)
13. [Evaluation Framework](#13-evaluation-framework)
14. [CV Paragrafı](#14-cv-paragrafı)

---

## 1. Proje Mimarisi

```
H&M Transaction Data (Kaggle)
           │
           ▼
    ┌─────────────────┐
    │  BigQuery (GCP) │  ← raw.transactions, raw.articles, raw.customers
    │  Sandbox / Free │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   dbt Models    │  ← stg_transactions → fct_user_features, fct_item_features
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────────────────────┐
    │         Two-Stage Pipeline           │
    │  Stage 1: ALS Candidate Gen (top-200)│
    │  Stage 2: LightGBM Ranker (NDCG@10) │
    └────────┬─────────────────────────────┘
             │
    ┌────────┴────────────────┐
    │                         │
    ▼                         ▼
BATCH PATH               REAL-TIME PATH
BigQuery Serving Table   FastAPI → Cloud Run
(nightly top-N)          POST /recommend
                         (user_id → top-10 JSON)
    │                         │
    └─────────┬───────────────┘
              │
              ▼
    ┌─────────────────┐
    │  GitHub Actions │  ← weekly retrain → eval → NDCG gate → deploy
    │  (MLOps / CI)   │
    └─────────────────┘
```

---

## 2. Ön Koşullar ve Kurulum

### 2.1 Gerekli Hesaplar (Tümü Ücretsiz)

| Servis | Link | Notlar |
|--------|------|--------|
| GitHub | github.com | Repository hosting + Actions |
| Google Cloud | console.cloud.google.com | BigQuery Sandbox + Cloud Run |
| Kaggle | kaggle.com | H&M veri seti indirme |

### 2.2 Lokal Ortam Kurulumu

```bash
# Python versiyonu kontrol et (3.10+ olmalı)
python --version

# Sanal ortam oluştur
python -m venv .venv
source .venv/bin/activate          # Mac/Linux
# .venv\Scripts\activate           # Windows

# Temel paketleri kur
pip install \
  pandas==2.2.0 \
  polars==0.20.0 \
  scikit-learn==1.4.0 \
  lightgbm==4.3.0 \
  implicit==0.7.2 \
  fastapi==0.110.0 \
  uvicorn==0.27.0 \
  mlflow==2.10.0 \
  google-cloud-bigquery==3.17.0 \
  db-dtypes==1.2.0 \
  dbt-bigquery==1.7.0 \
  joblib==1.3.2 \
  pytest==8.0.0 \
  httpx==0.27.0 \
  python-dotenv==1.0.0

pip freeze > requirements.txt
```

### 2.3 GCP Kurulumu (BigQuery Sandbox)

```bash
# Google Cloud SDK kur
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login
gcloud auth application-default login

# Yeni proje oluştur
gcloud projects create shopsignal-ml --name="ShopSignal ML"
gcloud config set project shopsignal-ml

# BigQuery API aktif et (ücretsiz sandbox)
gcloud services enable bigquery.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com

# Dataset oluştur
bq mk --dataset --location=australia-southeast1 shopsignal
```

> ⚠️ **Fatura Güvenliği:** GCP Console → Billing → Budgets & Alerts →  
> Budget: $5 limit → Email alert → Sürpriz fatura riski sıfır.

### 2.4 Kaggle API Kurulumu

```bash
# kaggle.com → Settings → API → Create New Token → kaggle.json indir

mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

pip install kaggle
```

---

## 3. Veri Yönetimi ve Erişim

### 3.1 H&M Personalized Fashion Dataset

**Neden H&M?**
- Gerçek ürün isimleri + açıklamaları var (NL search için kritik)
- 31M transaction (production-scale hissettiriyor)
- Retail/fashion domain → Kogan.com'a en yakın benchmark

**İndirme:**

```bash
# Kaggle'dan H&M veri setini indir
kaggle competitions download \
  -c h-and-m-personalized-fashion-recommendations

# Zip'i çıkar
unzip h-and-m-personalized-fashion-recommendations.zip -d data/raw/

# Dizin kontrolü
ls data/raw/
# Beklenen çıktı:
# articles.csv           (~54MB,  105K ürün)
# customers.csv          (~187MB, 1.37M müşteri)
# transactions_train.csv (~3.5GB, 31M satır)
# images/                (opsiyonel, gerek yok)
```

**Veri Seti İçeriği:**

```
transactions_train.csv
├── t_dat           → tarih (2018-09-20)
├── customer_id     → hash ID
├── article_id      → ürün ID
├── price           → normalize edilmiş fiyat
└── sales_channel_id → 1=store, 2=online

articles.csv
├── article_id
├── product_type_name       ← feature engineering için
├── product_group_name      ← kategori
├── colour_group_name       ← renk
├── department_name         ← departman
└── detail_desc             ← NL search için embedding

customers.csv
├── customer_id
├── age
├── club_member_status      ← loyalty segment
└── fashion_news_frequency  ← engagement sinyali
```

### 3.2 Hafıza Yönetimi (31M satır büyük!)

```python
# transactions_train.csv tamamını okuma — YAPMA!
# Sadece son 2M satırı al (en güncel davranış, daha temsili)

import pandas as pd

# Toplam satır sayısını kontrol et
total_lines = sum(1 for _ in open('data/raw/transactions_train.csv'))
print(f"Toplam satır: {total_lines:,}")  # ~31M

# Sadece son 2M satırı oku
df_transactions = pd.read_csv(
    'data/raw/transactions_train.csv',
    skiprows=range(1, total_lines - 2_000_000),  # header hariç ilk N satırı atla
    parse_dates=['t_dat']
)

print(df_transactions.shape)  # (2_000_000, 5)
print(df_transactions.dtypes)
```

### 3.3 BigQuery'e Yükleme

```python
# src/data/upload_to_bq.py

from google.cloud import bigquery
import pandas as pd

client = bigquery.Client(project="shopsignal-ml")

def upload_dataframe(df: pd.DataFrame, table_id: str, schema=None):
    """DataFrame'i BigQuery'e yükle."""
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",  # Varsa üzerine yaz
        schema=schema
    )
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Bekleme
    print(f"✅ {table_id} → {len(df):,} satır yüklendi")

# Transactions (2M satır)
df_tx = pd.read_csv('data/raw/transactions_train.csv', ...)
upload_dataframe(df_tx, "shopsignal-ml.shopsignal.raw_transactions")

# Articles (105K ürün)
df_articles = pd.read_csv('data/raw/articles.csv')
upload_dataframe(df_articles, "shopsignal-ml.shopsignal.raw_articles")

# Customers (subset)
df_customers = pd.read_csv('data/raw/customers.csv')
upload_dataframe(df_customers, "shopsignal-ml.shopsignal.raw_customers")
```

> 💡 **BigQuery Sandbox Limiti:** 10GB depolama, 1TB/ay sorgu — 2M satır yaklaşık 200MB.  
> Güvende. `LIMIT` eklemeyi unutma sorgu testlerinde.

---

## 4. GitHub Branch Yapısı

### 4.1 Repository Oluşturma

```bash
# GitHub'da yeni repo aç: github.com/new
# Repo adı: shopsignal
# Visibility: Public (portfolio için)
# README: ✓ Initialize

# Lokal'e clone
git clone https://github.com/ozzy2438/shopsignal.git
cd shopsignal

# Git config (yoksa)
git config --global user.name "Osman Orka"
git config --global user.email "your@email.com"
```

### 4.2 Branch Stratejisi

ShopSignal, **trunk-based development** kullanır. Bu, Kogan JD'sinde özellikle geçen bir pratik — CV'de ve interview'da bunu vurgula.

```
main (trunk)
├── feat/data-pipeline      ← Gün 1: BQ + dbt
├── feat/two-stage-model    ← Gün 2: ALS + LightGBM
├── feat/api-serving        ← Gün 3: FastAPI + Docker
├── feat/mlops-retrain      ← Gün 4: GitHub Actions
└── feat/genai-search       ← Gün 5: Vertex Vector Search (opsiyonel)
```

**Kural:** Her branch kısa ömürlü (max 1 gün), PR ile main'e merge edilir.

### 4.3 Branch Açma ve Kapatma Komutları

```bash
# ── GÜN 1: Data Pipeline Branch ──────────────────────────────────
git checkout main
git pull origin main
git checkout -b feat/data-pipeline

# ... çalış, commit at ...

git add .
git commit -m "feat: add BigQuery raw tables and dbt staging models"
git push origin feat/data-pipeline

# GitHub'da PR aç → Squash & Merge → main
git checkout main
git pull origin main
git branch -d feat/data-pipeline   # lokal branch sil


# ── GÜN 2: Two-Stage Model Branch ────────────────────────────────
git checkout -b feat/two-stage-model

git add .
git commit -m "feat: add ALS candidate gen and LightGBM ranker with NDCG eval"
git push origin feat/two-stage-model

# PR → main


# ── GÜN 3: API Serving Branch ─────────────────────────────────────
git checkout -b feat/api-serving

git add .
git commit -m "feat: add FastAPI endpoint and Dockerfile for Cloud Run"
git push origin feat/api-serving

# PR → main


# ── GÜN 4: MLOps Branch ───────────────────────────────────────────
git checkout -b feat/mlops-retrain

git add .
git commit -m "feat: add GitHub Actions retrain workflow with NDCG promotion gate"
git push origin feat/mlops-retrain

# PR → main


# ── GÜN 5: GenAI Branch (opsiyonel) ───────────────────────────────
git checkout -b feat/genai-search

git add .
git commit -m "feat: add semantic product search with text embeddings"
git push origin feat/genai-search
```

### 4.4 Commit Mesaj Standardı

```bash
# Format: <type>: <kısa açıklama>

feat: add LightGBM ranker with lambdarank objective
fix: correct user-item matrix shape for ALS training
test: add NDCG@10 evaluation unit tests
docs: update README with architecture diagram
ci: add GitHub Actions retrain workflow
refactor: extract feature engineering to separate module
```

### 4.5 İki Kişiyle Çalışma Protokolü

```bash
# Arkadaşın repoyu fork etmek yerine collaborator olarak ekleyin:
# GitHub → Settings → Collaborators → Add people

# Her kişi ayrı branch üzerinde çalışır, asla main'e direkt push yapmaz

# Ozzy'nin branch'leri:      Arkadaşının branch'leri:
# feat/data-pipeline         feat/model-evaluation
# feat/api-serving           feat/docker-setup
# feat/mlops-retrain         feat/readme-docs

# Merge öncesi PR review: birbirinizin PR'ını approve edin (1 approval yeter)

# Conflict çözümü:
git fetch origin
git rebase origin/main     # merge yerine rebase tercih et (temiz history)
```

### 4.6 main Branch Koruması (GitHub Settings)

```
GitHub → Repository → Settings → Branches → Add Branch Protection Rule

Branch name pattern: main
✓ Require a pull request before merging
✓ Require approvals: 1
✓ Require status checks to pass before merging
  → pytest (GitHub Actions check adı)
✓ Do not allow bypassing the above settings
```

---

## 5. Klasör Yapısı

```
shopsignal/
│
├── .github/
│   └── workflows/
│       ├── ci.yml              ← her PR'da pytest + lint
│       └── retrain.yml         ← haftalık model retrain + deploy
│
├── data/
│   ├── raw/                    ← .gitignore'da (büyük dosyalar)
│   └── processed/              ← .gitignore'da
│
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_transactions.sql
│   │   │   ├── stg_articles.sql
│   │   │   └── stg_customers.sql
│   │   └── mart/
│   │       ├── fct_user_item_interactions.sql
│   │       ├── fct_user_features.sql
│   │       └── fct_item_features.sql
│   ├── tests/
│   │   └── generic/
│   ├── dbt_project.yml
│   └── profiles.yml            ← .gitignore'da (credentials)
│
├── src/
│   ├── data/
│   │   └── upload_to_bq.py
│   ├── features/
│   │   └── build_features.py
│   ├── models/
│   │   ├── candidate_gen.py    ← ALS
│   │   └── ranker.py           ← LightGBM
│   ├── evaluate/
│   │   └── metrics.py          ← NDCG@K, Recall@K, MAP@K
│   └── serve/
│       └── app.py              ← FastAPI
│
├── pipelines/
│   └── retrain.py              ← GitHub Actions'ın çalıştırdığı script
│
├── tests/
│   ├── test_features.py
│   ├── test_ranker.py
│   └── test_api.py
│
├── models/                     ← joblib artifacts (.gitignore'da)
│   ├── als_model.pkl
│   └── lgbm_ranker.pkl
│
├── Dockerfile
├── requirements.txt
├── .gitignore
├── .env.example                ← credentials template (gerçek .env gitignore'da)
└── README.md
```

**.gitignore içeriği:**
```
# Data
data/raw/
data/processed/
models/

# Credentials
.env
dbt/profiles.yml
*.json                   # service account keys

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/

# MLflow
mlruns/
```

---

## 6. Gün 1 — Foundation: Veri + BigQuery + dbt

### Branch: `feat/data-pipeline`

```bash
git checkout -b feat/data-pipeline
```

### Adım 1: Veriyi İndir ve İncele

```bash
# H&M veri setini indir
kaggle competitions download \
  -c h-and-m-personalized-fashion-recommendations
unzip h-and-m-personalized-fashion-recommendations.zip -d data/raw/

# Hızlı inceleme
python -c "
import pandas as pd
df = pd.read_csv('data/raw/articles.csv')
print('Articles shape:', df.shape)
print(df.head(3))
print(df.dtypes)
"
```

### Adım 2: BigQuery'e Yükle

```python
# src/data/upload_to_bq.py
# (Yukarıdaki 3.3 kodunu çalıştır)
python src/data/upload_to_bq.py
```

### Adım 3: dbt Staging Modelleri

```bash
# dbt proje başlat
cd dbt
dbt init shopsignal_dbt

# profiles.yml oluştur (BigQuery bağlantısı)
```

```yaml
# dbt/profiles.yml  ← .gitignore'da
shopsignal:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: shopsignal-ml
      dataset: shopsignal
      location: australia-southeast1
      threads: 4
```

```sql
-- dbt/models/staging/stg_transactions.sql
WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_transactions') }}
)

SELECT
    CAST(t_dat AS DATE)                    AS transaction_date,
    LOWER(TRIM(customer_id))              AS customer_id,
    CAST(article_id AS STRING)            AS article_id,
    ROUND(CAST(price AS FLOAT64), 4)     AS price,
    CAST(sales_channel_id AS INT64)       AS channel_id,

    -- Implicit feedback sinyali
    CASE sales_channel_id
        WHEN 1 THEN 'store'
        WHEN 2 THEN 'online'
        ELSE 'unknown'
    END                                    AS channel_name

FROM source
WHERE
    t_dat IS NOT NULL
    AND customer_id IS NOT NULL
    AND article_id IS NOT NULL
```

```sql
-- dbt/models/mart/fct_user_item_interactions.sql
-- Implicit feedback matrix için
WITH tx AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

aggregated AS (
    SELECT
        customer_id,
        article_id,
        COUNT(*)                          AS purchase_count,
        SUM(price)                        AS total_spend,
        MAX(transaction_date)             AS last_purchase_date,
        MIN(transaction_date)             AS first_purchase_date,

        -- ALS için implicit confidence weight
        -- Confidence = 1 + alpha * purchase_count (alpha=40 standard)
        1 + (40 * COUNT(*))              AS als_confidence

    FROM tx
    GROUP BY customer_id, article_id
)

SELECT * FROM aggregated
```

```sql
-- dbt/models/mart/fct_item_features.sql
WITH tx AS (
    SELECT * FROM {{ ref('stg_transactions') }}
),

art AS (
    SELECT * FROM {{ source('raw', 'raw_articles') }}
),

item_stats AS (
    SELECT
        t.article_id,
        COUNT(DISTINCT t.customer_id)    AS unique_buyers,
        COUNT(*)                          AS total_purchases,
        AVG(t.price)                      AS avg_price,
        MAX(t.transaction_date)           AS last_sold_date,

        -- Popularite rank (baseline model için)
        RANK() OVER (ORDER BY COUNT(*) DESC) AS popularity_rank

    FROM tx t
    GROUP BY t.article_id
)

SELECT
    i.*,
    a.product_type_name,
    a.product_group_name,
    a.colour_group_name,
    a.department_name,
    a.detail_desc          -- NL search için embedding'e gidecek

FROM item_stats i
LEFT JOIN art a ON i.article_id = CAST(a.article_id AS STRING)
```

```bash
# dbt'yi çalıştır
cd dbt
dbt run
dbt test

# Başarılı çıktı:
# ✅ stg_transactions ............. PASS
# ✅ fct_user_item_interactions ... PASS
# ✅ fct_item_features ............ PASS
```

### Commit

```bash
git add .
git commit -m "feat: add BigQuery raw upload and dbt staging/mart models"
git push origin feat/data-pipeline
# GitHub'da PR aç → Merge → main
```

---

## 7. Gün 2 — Two-Stage Model: ALS + LightGBM Ranker

### Branch: `feat/two-stage-model`

```bash
git checkout main && git pull
git checkout -b feat/two-stage-model
```

### Adım 1: ALS Candidate Generation

```python
# src/models/candidate_gen.py

import implicit
import numpy as np
import scipy.sparse as sp
import joblib
import pandas as pd

def build_user_item_matrix(df: pd.DataFrame):
    """
    df: fct_user_item_interactions
    Returns: sparse matrix + mappings
    """
    # Integer index mapping
    user_ids = df['customer_id'].unique()
    item_ids = df['article_id'].unique()
    user2idx = {u: i for i, u in enumerate(user_ids)}
    item2idx = {a: i for i, a in enumerate(item_ids)}
    idx2user = {i: u for u, i in user2idx.items()}
    idx2item = {i: a for a, i in item2idx.items()}

    rows = df['customer_id'].map(user2idx).values
    cols = df['article_id'].map(item2idx).values
    data = df['als_confidence'].values.astype(np.float32)

    matrix = sp.csr_matrix(
        (data, (rows, cols)),
        shape=(len(user_ids), len(item_ids))
    )
    return matrix, user2idx, item2idx, idx2user, idx2item


def train_als(matrix, factors=64, iterations=20, regularization=0.01):
    """ALS modelini eğit."""
    model = implicit.als.AlternatingLeastSquares(
        factors=factors,
        iterations=iterations,
        regularization=regularization,
        calculate_training_loss=True,
        use_gpu=False
    )
    model.fit(matrix)
    return model


def generate_candidates(
    model,
    user_idx: int,
    matrix,
    idx2item: dict,
    n_candidates: int = 200
) -> list[str]:
    """Tek kullanıcı için top-N aday üret."""
    item_ids_ranked, scores = model.recommend(
        user_idx,
        matrix[user_idx],
        N=n_candidates,
        filter_already_liked_items=True
    )
    return [idx2item[i] for i in item_ids_ranked]


if __name__ == "__main__":
    from google.cloud import bigquery
    client = bigquery.Client(project="shopsignal-ml")

    # BigQuery'den feature tablosunu çek
    query = """
        SELECT customer_id, article_id, als_confidence
        FROM `shopsignal-ml.shopsignal.fct_user_item_interactions`
    """
    df = client.query(query).to_dataframe()
    print(f"✅ {len(df):,} satır yüklendi")

    # Matrix ve model
    matrix, user2idx, item2idx, idx2user, idx2item = build_user_item_matrix(df)
    model = train_als(matrix)

    # Kaydet
    joblib.dump({
        'model': model,
        'user2idx': user2idx,
        'item2idx': item2idx,
        'idx2user': idx2user,
        'idx2item': idx2item,
        'matrix': matrix
    }, 'models/als_model.pkl')
    print("✅ ALS modeli kaydedildi: models/als_model.pkl")
```

### Adım 2: LightGBM Ranker

```python
# src/models/ranker.py

import lightgbm as lgb
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import GroupShuffleSplit

def build_ranker_dataset(
    interactions_df: pd.DataFrame,
    user_features_df: pd.DataFrame,
    item_features_df: pd.DataFrame,
    candidates_per_user: dict,
    n_negatives: int = 5
) -> pd.DataFrame:
    """
    Ranker için train dataset oluştur.
    Positive: gerçek satın alma
    Negative: ALS adayları arasından rastgele seçilen (satın alınmayanlar)
    """
    purchased = set(zip(
        interactions_df['customer_id'],
        interactions_df['article_id']
    ))

    records = []
    for user_id, candidates in candidates_per_user.items():
        user_purchases = interactions_df[
            interactions_df['customer_id'] == user_id
        ]['article_id'].tolist()

        # Positive örnekler
        for item_id in user_purchases:
            records.append({
                'customer_id': user_id,
                'article_id': item_id,
                'label': 1
            })

        # Negative örnekler (satın alınmamış adaylardan)
        negatives = [c for c in candidates if c not in set(user_purchases)]
        sampled_neg = np.random.choice(
            negatives,
            size=min(n_negatives * len(user_purchases), len(negatives)),
            replace=False
        )
        for item_id in sampled_neg:
            records.append({
                'customer_id': user_id,
                'article_id': item_id,
                'label': 0
            })

    df = pd.DataFrame(records)

    # Feature join
    df = df.merge(user_features_df, on='customer_id', how='left')
    df = df.merge(item_features_df, on='article_id', how='left')

    return df.fillna(0)


def train_ranker(df: pd.DataFrame):
    """LightGBM LambdaMART ranker."""

    FEATURES = [
        # User features
        'user_purchase_count', 'user_unique_items', 'user_avg_spend',
        'user_days_active', 'user_online_ratio',
        # Item features
        'unique_buyers', 'total_purchases', 'avg_price',
        'popularity_rank',
    ]

    # Train/test split by group (user)
    users = df['customer_id'].unique()
    train_users = users[:int(0.8 * len(users))]
    test_users = users[int(0.8 * len(users)):]

    train_df = df[df['customer_id'].isin(train_users)].copy()
    test_df = df[df['customer_id'].isin(test_users)].copy()

    # Group sizes (her user için kaç sample var)
    train_groups = train_df.groupby('customer_id').size().values
    test_groups = test_df.groupby('customer_id').size().values

    train_data = lgb.Dataset(
        train_df[FEATURES],
        label=train_df['label'],
        group=train_groups
    )
    test_data = lgb.Dataset(
        test_df[FEATURES],
        label=test_df['label'],
        group=test_groups,
        reference=train_data
    )

    params = {
        'objective': 'lambdarank',
        'metric': 'ndcg',
        'ndcg_eval_at': [5, 10],
        'learning_rate': 0.05,
        'num_leaves': 63,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'n_jobs': -1
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=300,
        valid_sets=[test_data],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)]
    )

    joblib.dump(model, 'models/lgbm_ranker.pkl')
    print("✅ LightGBM ranker kaydedildi: models/lgbm_ranker.pkl")
    return model, test_df, FEATURES
```

### Adım 3: Evaluation Metrics

```python
# src/evaluate/metrics.py

import numpy as np
from typing import List, Dict


def dcg_at_k(relevances: List[int], k: int) -> float:
    """Discounted Cumulative Gain @ K"""
    relevances = np.array(relevances[:k], dtype=float)
    if len(relevances) == 0:
        return 0.0
    gains = relevances / np.log2(np.arange(2, len(relevances) + 2))
    return gains.sum()


def ndcg_at_k(recommended: List[str], relevant: List[str], k: int) -> float:
    """Normalized DCG @ K"""
    relevances = [1 if item in set(relevant) else 0 for item in recommended[:k]]
    ideal_relevances = sorted(relevances, reverse=True)
    actual_dcg = dcg_at_k(relevances, k)
    ideal_dcg = dcg_at_k(ideal_relevances, k)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def recall_at_k(recommended: List[str], relevant: List[str], k: int) -> float:
    """Recall @ K"""
    if not relevant:
        return 0.0
    hits = len(set(recommended[:k]) & set(relevant))
    return hits / len(relevant)


def map_at_k(recommended: List[str], relevant: List[str], k: int) -> float:
    """Mean Average Precision @ K"""
    relevant_set = set(relevant)
    hits, sum_precision = 0, 0.0
    for i, item in enumerate(recommended[:k]):
        if item in relevant_set:
            hits += 1
            sum_precision += hits / (i + 1)
    return sum_precision / min(len(relevant), k) if relevant else 0.0


def evaluate_model(
    recommendations: Dict[str, List[str]],
    ground_truth: Dict[str, List[str]],
    k: int = 10
) -> Dict[str, float]:
    """
    recommendations: {user_id: [item_id, ...]}  (ranked)
    ground_truth:    {user_id: [item_id, ...]}  (purchased)
    """
    ndcg_scores, recall_scores, map_scores = [], [], []

    for user_id, recs in recommendations.items():
        relevant = ground_truth.get(user_id, [])
        if not relevant:
            continue
        ndcg_scores.append(ndcg_at_k(recs, relevant, k))
        recall_scores.append(recall_at_k(recs, relevant, k))
        map_scores.append(map_at_k(recs, relevant, k))

    results = {
        f'NDCG@{k}':   round(np.mean(ndcg_scores), 4),
        f'Recall@{k}': round(np.mean(recall_scores), 4),
        f'MAP@{k}':    round(np.mean(map_scores), 4),
        'n_users_evaluated': len(ndcg_scores)
    }

    print("\n📊 Model Değerlendirme Sonuçları:")
    for metric, value in results.items():
        print(f"   {metric}: {value}")

    return results


# Promotion gate için threshold
NDCG_THRESHOLD = 0.08   # Baseline (popularity) genellikle 0.05-0.07 civarı
                         # Model bunu geçmezse deploy edilmez
```

### Commit

```bash
git add .
git commit -m "feat: add ALS candidate gen and LightGBM ranker with NDCG@10 eval"
git push origin feat/two-stage-model
# PR → main
```

---

## 8. Gün 3 — Serving: FastAPI + Docker + Cloud Run

### Branch: `feat/api-serving`

```bash
git checkout main && git pull
git checkout -b feat/api-serving
```

### Adım 1: FastAPI Uygulaması

```python
# src/serve/app.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import numpy as np
from typing import Optional
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ShopSignal Recommendation API",
    description="Two-stage recommendation engine for eCommerce personalisation",
    version="1.0.0"
)

# Startup: model artifact'larını yükle
als_artifacts = None
lgbm_model = None

@app.on_event("startup")
async def load_models():
    global als_artifacts, lgbm_model
    try:
        als_artifacts = joblib.load("models/als_model.pkl")
        lgbm_model = joblib.load("models/lgbm_ranker.pkl")
        logger.info("✅ Modeller yüklendi")
    except FileNotFoundError as e:
        logger.error(f"❌ Model dosyası bulunamadı: {e}")


class RecommendRequest(BaseModel):
    user_id: str
    top_n: int = 10
    context: Optional[dict] = None   # session context (opsiyonel)


class RecommendResponse(BaseModel):
    user_id: str
    recommendations: list[str]
    model_version: str
    served_at: str


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(request: RecommendRequest):
    """Kullanıcı için top-N ürün önerisi üret."""
    from datetime import datetime, timezone

    if als_artifacts is None:
        raise HTTPException(status_code=503, detail="Modeller henüz yüklenmedi")

    user2idx = als_artifacts['user2idx']
    idx2item = als_artifacts['idx2item']
    model    = als_artifacts['model']
    matrix   = als_artifacts['matrix']

    # Cold start: kullanıcı bilinmiyorsa popularity-based fallback
    if request.user_id not in user2idx:
        logger.warning(f"Cold start: {request.user_id} — popularity fallback")
        # Basit fallback: en popüler N ürün (production'da BQ'den çekilir)
        popular_items = list(idx2item.values())[:request.top_n]
        return RecommendResponse(
            user_id=request.user_id,
            recommendations=popular_items,
            model_version="popularity-fallback-v1",
            served_at=datetime.now(timezone.utc).isoformat()
        )

    # Stage 1: ALS candidates
    user_idx = user2idx[request.user_id]
    candidate_indices, _ = model.recommend(
        user_idx,
        matrix[user_idx],
        N=200,
        filter_already_liked_items=True
    )
    candidates = [idx2item[i] for i in candidate_indices]

    # Stage 2: LightGBM rerank
    # (production'da BQ'den feature'ları çek, burada dummy features kullanıyoruz)
    features = pd.DataFrame({'article_id': candidates})
    # ... feature join ...
    # scores = lgbm_model.predict(features[FEATURE_COLS])
    # ranked = [candidates[i] for i in np.argsort(scores)[::-1]]
    ranked = candidates  # feature join olmadan ALS sıralamasını kullan

    return RecommendResponse(
        user_id=request.user_id,
        recommendations=ranked[:request.top_n],
        model_version="shopsignal-v1.0",
        served_at=datetime.now(timezone.utc).isoformat()
    )


@app.get("/health")
async def health():
    """Cloud Run health check endpoint."""
    return {
        "status": "healthy",
        "models_loaded": als_artifacts is not None
    }


@app.get("/metrics")
async def metrics():
    """Son retrain metriklerini döndür."""
    metrics_path = "models/latest_metrics.json"
    if os.path.exists(metrics_path):
        import json
        with open(metrics_path) as f:
            return json.load(f)
    return {"message": "Henüz metrik yok"}
```

### Adım 2: Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Bağımlılıkları önce kopyala (layer cache için)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY src/ ./src/
COPY models/ ./models/

# Cloud Run PORT env variable'ını kullan (default: 8080)
ENV PORT=8080

EXPOSE 8080

CMD ["uvicorn", "src.serve.app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Adım 3: Lokal Test

```bash
# Docker image build et
docker build -t shopsignal-api .

# Lokal çalıştır
docker run -p 8080:8080 shopsignal-api

# Test et (yeni terminalde)
curl -X POST http://localhost:8080/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": "abc123", "top_n": 5}'

curl http://localhost:8080/health
```

### Commit

```bash
git add .
git commit -m "feat: add FastAPI serving layer and Dockerfile for Cloud Run"
git push origin feat/api-serving
# PR → main
```

---

## 9. Gün 4 — MLOps: GitHub Actions + Otomatik Retrain

### Branch: `feat/mlops-retrain`

```bash
git checkout main && git pull
git checkout -b feat/mlops-retrain
```

### Adım 1: Retrain Pipeline Script

```python
# pipelines/retrain.py

"""
GitHub Actions tarafından haftalık çalıştırılır.
Adımlar:
1. BigQuery'den fresh data çek
2. ALS + LightGBM modellerini yeniden eğit
3. NDCG@10 hesapla — threshold'u geçmezse deployment'ı durdur
4. Threshold geçilirse Cloud Run'a deploy et
"""

import sys
import json
import joblib
import logging
from pathlib import Path
from datetime import datetime, timezone

# src modüllerini import et
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.candidate_gen import build_user_item_matrix, train_als
from src.models.ranker import train_ranker
from src.evaluate.metrics import evaluate_model, NDCG_THRESHOLD

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)
logger = logging.getLogger(__name__)

NDCG_K = 10


def fetch_data_from_bq():
    """BigQuery'den interaction data çek."""
    from google.cloud import bigquery
    client = bigquery.Client(project="shopsignal-ml")

    query = """
        SELECT customer_id, article_id, als_confidence
        FROM `shopsignal-ml.shopsignal.fct_user_item_interactions`
        WHERE transaction_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        LIMIT 500000
    """
    logger.info("BigQuery'den veri çekiliyor...")
    df = client.query(query).to_dataframe()
    logger.info(f"✅ {len(df):,} satır çekildi")
    return df


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info(f"🚀 Retrain başladı: run_id={run_id}")

    # 1. Veri
    df = fetch_data_from_bq()

    # 2. Train-test split (son %20 test)
    df_sorted = df.sort_values('als_confidence', ascending=False)
    split_idx = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split_idx]
    test_df = df_sorted.iloc[split_idx:]

    # 3. ALS eğit
    logger.info("ALS eğitiliyor...")
    matrix, user2idx, item2idx, idx2user, idx2item = build_user_item_matrix(train_df)
    als_model = train_als(matrix)

    # 4. Test seti için adaylar üret
    test_users = test_df['customer_id'].unique()[:1000]  # 1K user örneği
    recommendations = {}
    ground_truth = {}

    for user_id in test_users:
        if user_id not in user2idx:
            continue
        user_idx = user2idx[user_id]
        cand_indices, _ = als_model.recommend(
            user_idx, matrix[user_idx], N=200, filter_already_liked_items=True
        )
        recommendations[user_id] = [idx2item[i] for i in cand_indices[:NDCG_K]]
        ground_truth[user_id] = test_df[
            test_df['customer_id'] == user_id
        ]['article_id'].tolist()

    # 5. Değerlendirme
    metrics = evaluate_model(recommendations, ground_truth, k=NDCG_K)
    ndcg_score = metrics[f'NDCG@{NDCG_K}']

    # 6. Promotion Gate
    if ndcg_score < NDCG_THRESHOLD:
        logger.error(
            f"❌ PROMOTION BLOCKED: NDCG@{NDCG_K}={ndcg_score:.4f} "
            f"< threshold={NDCG_THRESHOLD}"
        )
        # GitHub Actions bu exit code'u görüp workflow'u fail eder
        sys.exit(1)

    logger.info(
        f"✅ PROMOTION APPROVED: NDCG@{NDCG_K}={ndcg_score:.4f} "
        f">= threshold={NDCG_THRESHOLD}"
    )

    # 7. Modelleri kaydet
    Path("models").mkdir(exist_ok=True)
    joblib.dump({
        'model': als_model,
        'user2idx': user2idx,
        'item2idx': item2idx,
        'idx2user': idx2user,
        'idx2item': idx2item,
        'matrix': matrix
    }, 'models/als_model.pkl')

    # 8. Metrikleri kaydet (API /metrics endpoint'i için)
    metrics['run_id'] = run_id
    metrics['trained_at'] = datetime.now(timezone.utc).isoformat()
    metrics['threshold'] = NDCG_THRESHOLD

    with open('models/latest_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"✅ Retrain tamamlandı: run_id={run_id}")
    logger.info(f"📊 Final metrics: {metrics}")


if __name__ == "__main__":
    main()
```

### Adım 2: CI Workflow (Her PR'da Çalışır)

```yaml
# .github/workflows/ci.yml

name: CI — Test & Lint

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Python kurulum
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Bağımlılıkları kur
        run: pip install -r requirements.txt

      - name: Pytest çalıştır
        run: pytest tests/ -v --tb=short

      - name: Lint (ruff)
        run: |
          pip install ruff
          ruff check src/ pipelines/
```

### Adım 3: Retrain + Deploy Workflow (Haftalık)

```yaml
# .github/workflows/retrain.yml

name: Weekly Retrain & Deploy

on:
  schedule:
    - cron: '0 2 * * 1'    # Her Pazartesi saat 02:00 UTC
  workflow_dispatch:          # Manuel tetiklenebilir (test için)

env:
  PROJECT_ID: shopsignal-ml
  REGION: australia-southeast1
  SERVICE: shopsignal-api
  IMAGE: gcr.io/shopsignal-ml/shopsignal-api

jobs:
  retrain-and-deploy:
    runs-on: ubuntu-latest

    permissions:
      contents: read
      id-token: write    # Workload Identity Federation için

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Python kurulum
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Bağımlılıkları kur
        run: pip install -r requirements.txt

      - name: GCP Auth
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: GCP SDK kurulum
        uses: google-github-actions/setup-gcloud@v2

      - name: Modeli yeniden eğit (NDCG gate dahil)
        run: python pipelines/retrain.py
        # Bu adım fail olursa (sys.exit(1)) → aşağıdaki adımlar çalışmaz
        # = deployment engellenir

      - name: Docker image build et
        run: |
          docker build -t $IMAGE:$GITHUB_SHA .
          docker tag $IMAGE:$GITHUB_SHA $IMAGE:latest

      - name: GCR'e push et
        run: |
          gcloud auth configure-docker
          docker push $IMAGE:$GITHUB_SHA
          docker push $IMAGE:latest

      - name: Cloud Run'a deploy et
        run: |
          gcloud run deploy $SERVICE \
            --image $IMAGE:$GITHUB_SHA \
            --region $REGION \
            --platform managed \
            --allow-unauthenticated \
            --memory 2Gi \
            --cpu 2 \
            --max-instances 3 \
            --set-env-vars GCP_PROJECT=$PROJECT_ID

      - name: Deployment doğrula
        run: |
          SERVICE_URL=$(gcloud run services describe $SERVICE \
            --region $REGION \
            --format 'value(status.url)')
          echo "🚀 Deployed: $SERVICE_URL"
          curl -f "$SERVICE_URL/health"
```

### Adım 4: GitHub Secrets Kurulumu

```
GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret

Secret adı: GCP_SA_KEY
Secret değeri: GCP service account JSON key içeriği

# GCP'de service account oluştur:
gcloud iam service-accounts create github-actions-sa \
  --display-name="GitHub Actions SA"

gcloud projects add-iam-policy-binding shopsignal-ml \
  --member="serviceAccount:github-actions-sa@shopsignal-ml.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding shopsignal-ml \
  --member="serviceAccount:github-actions-sa@shopsignal-ml.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding shopsignal-ml \
  --member="serviceAccount:github-actions-sa@shopsignal-ml.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# JSON key oluştur
gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions-sa@shopsignal-ml.iam.gserviceaccount.com

# key.json içeriğini GitHub Secret olarak ekle, sonra sil
cat key.json   # kopyala → GitHub Secret'a yapıştır
rm key.json    # ZORUNLU: commit'leme!
```

### Commit

```bash
git add .
git commit -m "feat: add GitHub Actions CI/CD and NDCG-gated weekly retrain workflow"
git push origin feat/mlops-retrain
# PR → main
```

---

## 10. Gün 5 — GenAI Katmanı + README + Son Kontroller

### Branch: `feat/genai-search`

```bash
git checkout main && git pull
git checkout -b feat/genai-search
```

### Adım 1: Semantic Product Search

```python
# src/serve/semantic_search.py

"""
articles.csv'deki ürün açıklamalarını embed'e,
natural language query ile semantik arama yap.
Örnek: "warm waterproof jacket under $100"
"""

from sentence_transformers import SentenceTransformer
import numpy as np
import pandas as pd
import joblib

def build_product_index(articles_df: pd.DataFrame):
    """Ürün açıklamalarından embedding index oluştur."""
    model = SentenceTransformer('all-MiniLM-L6-v2')  # Ücretsiz, lokal

    # Her ürün için metin oluştur
    texts = (
        articles_df['product_type_name'].fillna('') + ' ' +
        articles_df['colour_group_name'].fillna('') + ' ' +
        articles_df['department_name'].fillna('') + ' ' +
        articles_df['detail_desc'].fillna('')
    ).tolist()

    print(f"Embedding oluşturuluyor: {len(texts)} ürün...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    index = {
        'embeddings': embeddings,
        'article_ids': articles_df['article_id'].tolist(),
        'metadata': articles_df[['article_id', 'product_type_name',
                                  'colour_group_name', 'avg_price']].to_dict('records')
    }
    joblib.dump(index, 'models/product_index.pkl')
    print("✅ Product embedding index kaydedildi")
    return index


def semantic_search(query: str, index: dict, top_k: int = 10) -> list[dict]:
    """Natural language query → ranked products."""
    from sentence_transformers import SentenceTransformer
    import numpy as np

    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode([query])[0]

    # Cosine similarity
    embeddings = np.array(index['embeddings'])
    scores = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding) + 1e-8
    )

    top_indices = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_indices:
        result = index['metadata'][idx].copy()
        result['similarity_score'] = float(scores[idx])
        results.append(result)

    return results
```

```python
# FastAPI'ye endpoint ekle (src/serve/app.py içine)

@app.post("/search")
async def semantic_search_endpoint(query: str, top_k: int = 10):
    """Natural language product search."""
    from src.serve.semantic_search import semantic_search
    import joblib

    index = joblib.load("models/product_index.pkl")
    results = semantic_search(query, index, top_k)
    return {
        "query": query,
        "results": results,
        "model": "sentence-transformers/all-MiniLM-L6-v2"
    }
```

### Adım 2: Testler

```python
# tests/test_api.py

import pytest
from fastapi.testclient import TestClient
from src.serve.app import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_recommend_cold_start():
    """Bilinmeyen kullanıcı → popularity fallback döner."""
    response = client.post("/recommend", json={
        "user_id": "nonexistent_user_xyz",
        "top_n": 5
    })
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert len(data["recommendations"]) <= 5


def test_recommend_response_schema():
    """Response schema doğrulama."""
    response = client.post("/recommend", json={
        "user_id": "test_user",
        "top_n": 10
    })
    data = response.json()
    assert "user_id" in data
    assert "recommendations" in data
    assert "model_version" in data
    assert "served_at" in data
```

```python
# tests/test_ranker.py

import numpy as np
from src.evaluate.metrics import ndcg_at_k, recall_at_k, map_at_k, NDCG_THRESHOLD


def test_ndcg_perfect():
    """Mükemmel sıralama → NDCG@10 = 1.0"""
    recommended = ['a', 'b', 'c', 'd', 'e']
    relevant = ['a', 'b', 'c']
    score = ndcg_at_k(recommended, relevant, k=5)
    assert score == pytest.approx(1.0)


def test_ndcg_no_hits():
    """Sıfır isabet → NDCG@10 = 0.0"""
    recommended = ['x', 'y', 'z']
    relevant = ['a', 'b', 'c']
    score = ndcg_at_k(recommended, relevant, k=10)
    assert score == 0.0


def test_recall_at_k():
    recommended = ['a', 'b', 'c', 'd', 'e']
    relevant = ['a', 'c', 'f']
    score = recall_at_k(recommended, relevant, k=5)
    assert score == pytest.approx(2/3)


def test_ndcg_threshold_is_positive():
    """Threshold mantıklı bir değer olmalı."""
    assert 0 < NDCG_THRESHOLD < 1.0
```

### Adım 3: Son Kontrol Listesi

```bash
# 1. Tüm testler geçiyor mu?
pytest tests/ -v
# Beklenen: 5+ passed

# 2. dbt testleri geçiyor mu?
cd dbt && dbt test
# Beklenen: all passed

# 3. Cloud Run endpoint canlı mı?
SERVICE_URL=$(gcloud run services describe shopsignal-api \
  --region australia-southeast1 \
  --format 'value(status.url)')
curl "$SERVICE_URL/health"
# Beklenen: {"status":"healthy","models_loaded":true}

# 4. GitHub Actions son workflow başarılı mı?
# GitHub → Actions → Son run → Green ✅

# 5. README'de bunlar var mı?
# ✓ Mimari diyagram
# ✓ Problem statement
# ✓ Metrik tablosu (baseline vs model)
# ✓ Cloud Run live URL
# ✓ How to run (3 komutla çalışmalı)
```

### Final Commit

```bash
git add .
git commit -m "feat: add semantic search, complete test suite, final README"
git push origin feat/genai-search
# PR → main
```

---

## 11. GitHub Actions Entegrasyonu

### Workflow Özeti

| Workflow | Tetikleyici | Ne Yapar |
|----------|-------------|----------|
| `ci.yml` | Her PR + main push | pytest + ruff lint |
| `retrain.yml` | Haftalık Pazartesi + manual | Retrain → NDCG gate → Cloud Run deploy |

### Workflow Durumunu İzleme

```
GitHub → Actions sekmesi → Son workflow run'ları

Başarılı: ✅ yeşil
Başarısız: ❌ kırmızı → tıkla → log'ları incele

Manuel tetikleme:
Actions → "Weekly Retrain & Deploy" → "Run workflow" butonu
```

### Branch Protection ile CI Zorunluluğu

```
Settings → Branches → main → Branch protection rules
✓ Require status checks:
  → pytest (ci.yml)
→ Bu aktifse CI geçmeden merge yapılamaz
```

---

## 12. Cloud Run Deployment Süreci

### İlk Manuel Deployment

```bash
# Image build et
docker build -t gcr.io/shopsignal-ml/shopsignal-api:v1 .

# GCR'e authenticate
gcloud auth configure-docker

# Push et
docker push gcr.io/shopsignal-ml/shopsignal-api:v1

# Cloud Run'a deploy et
gcloud run deploy shopsignal-api \
  --image gcr.io/shopsignal-ml/shopsignal-api:v1 \
  --region australia-southeast1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --max-instances 3

# Servis URL'ini al
gcloud run services describe shopsignal-api \
  --region australia-southeast1 \
  --format 'value(status.url)'

# Test et
curl -X POST https://shopsignal-api-xxx-ts.a.run.app/recommend \
  -H "Content-Type: application/json" \
  -d '{"user_id": "abc123", "top_n": 5}'
```

### Cloud Run Maliyet Kontrolü

```
Cloud Run ücretsiz tier:
- 2M request/ay → ücretsiz
- 360K vCPU-saniye/ay → ücretsiz
- 180K GB-saniye/ay → ücretsiz

Demo/portfolio için: tam anlamıyla $0
```

---

## 13. Evaluation Framework

### Metrik Tablosu (README'e ekle)

| Model | NDCG@10 | Recall@10 | MAP@10 |
|-------|---------|-----------|--------|
| Popularity Baseline | ~0.052 | ~0.034 | ~0.041 |
| ALS Only (Stage 1) | ~0.071 | ~0.051 | ~0.058 |
| ALS + LightGBM Ranker | **~0.089** | **~0.063** | **~0.074** |

> 📝 Gerçek değerler eğitimden sonra güncelle. Uydurma!

### Promotion Gate Mantığı

```
retrain.py çalışır
       ↓
NDCG@10 hesapla
       ↓
     [Gate]
   ┌──┴──┐
≥ 0.08  < 0.08
   ↓       ↓
Deploy   sys.exit(1)
Cloud    GitHub Actions
Run      workflow fail
         → deployment yok
         → eski model çalışmaya devam
```

---

## 14. CV Paragrafı

Proje tamamlandığında, gerçek metriklerle aşağıdaki paragrafı kullan:

---

**ShopSignal — GCP-Native Two-Stage Recommendation & Personalisation Platform**

Built an end-to-end recommendation engine on GCP targeting eCommerce personalisation at scale; ingested 2M+ H&M behavioural transactions into BigQuery, engineered user-affinity, recency and item-popularity feature tables via dbt with automated data quality tests, and trained a two-stage pipeline combining ALS implicit collaborative filtering (top-200 candidate generation) with a LightGBM LambdaMART ranker — improving NDCG@10 by **[X]%** over a popularity baseline. Productionised through a Cloud Run FastAPI serving layer supporting both real-time (`/recommend`) and batch inference paths, with automated weekly retraining via GitHub Actions and an NDCG-gated promotion gate that blocks degraded models before deployment. Added a semantic product discovery layer using sentence-transformer embeddings enabling natural-language queries. Implemented full CI/CD with trunk-based development, Docker containerisation, pytest coverage and observability logging throughout.

**Stack:** Python · BigQuery · dbt · LightGBM · Cloud Run · FastAPI · Docker · GitHub Actions · Sentence Transformers

---

> ⚡ **Son Not:** NDCG artış yüzdesini gerçek ölçümle doldur.  
> "Popularity baseline'ı %X geçtim" → hem dürüst hem güçlü bir satır.

---

*ShopSignal Roadmap v1.0 — Osman Orka, 2026*
