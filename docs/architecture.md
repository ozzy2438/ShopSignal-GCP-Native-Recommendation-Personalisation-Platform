# ShopSignal — System Architecture

## High-Level Data Flow

```
H&M Transaction Data (Kaggle)
           │
           ▼
    ┌─────────────────────────────┐
    │  BigQuery Sandbox (GCP)     │  raw.transactions · raw.articles · raw.customers
    └────────────┬────────────────┘
                 │ dbt run
                 ▼
    ┌─────────────────────────────┐
    │      dbt Models             │
    │  stg_transactions           │
    │  stg_articles               │  → fct_user_item_interactions
    │  stg_customers              │  → fct_user_features
    │                             │  → fct_item_features
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────────────────┐
    │         Two-Stage Pipeline              │
    │                                         │
    │  Stage 1 — ALS (implicit library)       │
    │  · User-item matrix from BigQuery        │
    │  · Factors=64, Iterations=15            │
    │  · Top-200 candidates per user          │
    │                                         │
    │  Stage 2 — LightGBM LambdaMART          │
    │  · Features: user + item + context      │
    │  · Objective: lambdarank                │
    │  · Metric: NDCG@10                      │
    │  · Re-rank 200 → top-10                 │
    └──────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  BATCH PATH             REAL-TIME PATH
  BigQuery Serving       FastAPI → Docker → Cloud Run
  Table (nightly)        POST /recommend
  pre-computed top-N     user_id → top-10 JSON
        │                     │
        └──────────┬──────────┘
                   ▼
    ┌─────────────────────────┐
    │     GitHub Actions      │
    │  Weekly retrain         │
    │  → eval → NDCG gate     │
    │  → deploy if gate pass  │
    └─────────────────────────┘
```

## Component Responsibilities

### BigQuery
- Raw data ingestion (H&M CSV → BigQuery tables)
- dbt transformation (staging views → mart tables)
- Batch serving table (nightly pre-computed recommendations)
- Free Sandbox tier sufficient for development

### dbt
- Handles all SQL transformation logic
- Staging layer: type casting, null filtering, column renaming
- Mart layer: feature engineering, aggregation, joins
- Tests: unique, not_null, accepted_values assertions

### ALS (implicit library)
- Collaborative filtering on user-item interaction matrix
- Produces top-200 candidates per user (recall-focused)
- Fast approximate nearest-neighbour lookup
- Output: candidate list per user

### LightGBM LambdaMART
- List-wise ranking on ALS candidate list
- Features: user demographics, item attributes, interaction signals
- Optimises NDCG@10 directly
- Output: ranked top-10 list per user

### FastAPI
- Serves recommendations in real-time
- `/health` for Cloud Run health probes; `/version` exposes loaded model metadata
- `/recommend` and `/recommend/batch` run the two-stage flow: ALS top-200 →
  LightGBM re-rank → top-N, with popularity fallback for cold-start users
- Models load from `SHOPSIGNAL_MODEL_DIR` (ALS + LightGBM + popularity + feature
  tables + schema); mock data when no bundle so CI runs without the dataset
- Future: read pre-computed candidates from the BigQuery batch serving table

### GitHub Actions
- PR quality gates: lint, format, test, Docker build
- Merge to main: build release candidate, tag Docker image
- Scheduled retrain: data validation → train → evaluate → NDCG gate → deploy

## Technology Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Candidate gen | ALS (implicit) | Fast, proven, handles implicit feedback |
| Ranker | LightGBM LambdaMART | Direct NDCG optimisation, fast training |
| Transformation | dbt | SQL-native, testable, version-controlled |
| Serving | FastAPI | High performance, async, OpenAPI out of the box |
| Container | Docker (multi-stage) | Reproducible, lean runtime image |
| Cloud | Cloud Run | Serverless, scales to zero, managed |
| Auth | Workload Identity Federation | Keyless, no long-lived credentials |
| CI/CD | GitHub Actions | Native to GitHub, free for public repos |

## Security Design

- No service-account JSON keys committed to Git
- Workload Identity Federation for Cloud Run → GitHub Actions authentication
- Non-root Docker container user
- Environment-specific secrets via GitHub Environments
- `data/`, `models/`, `.env` always in `.gitignore`
