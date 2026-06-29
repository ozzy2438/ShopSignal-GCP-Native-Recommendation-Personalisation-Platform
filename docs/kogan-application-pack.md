# Kogan Machine Learning Engineer Application Pack

All statements below are limited to implemented code and validated local evidence.

## CV bullets

- Built a leakage-safe two-stage recommender over **15 million H&M transactions**
  (**899,083 users × 62,078 items**), combining implicit ALS top-200 retrieval with
  LightGBM LambdaMART re-ranking; improved untouched-test **NDCG@10 by ~6%** and
  **Recall@10 by ~12%** over raw ALS.
- Production-engineered top-10 inference with model-bundle persistence, train-only feature
  assembly, popularity cold-start fallback, and FastAPI single/batch endpoints (up to
  **1,000 users per request**); validated the serving path within a **142-test** unit,
  integration, and smoke suite.
- Implemented retail data validation and chronological evaluation across
  **11.6M/1.8M/1.6M train/validation/test events**, then packaged the service in a non-root
  Docker image with GitHub Actions lint, test, build, and health gates; ALS candidate
  Recall@200 beat popularity by **~43%** on the tuning sample.

## Project summary

ShopSignal is a GCP-oriented retail personalisation project that turns implicit purchase
history into top-10 recommendations through ALS candidate retrieval and LightGBM
LambdaMART re-ranking. It was evaluated with a leakage-safe chronological split over 15
million H&M transactions, where re-ranking improved test NDCG@10 by approximately 6% and
Recall@10 by approximately 12% over raw ALS. The project includes popularity fallback for
cold-start users, model persistence, FastAPI single and batch serving, Docker packaging,
BigQuery/dbt-oriented SQL, and GitHub Actions quality/release simulation. Cloud Run
deployment is prepared but not live.

## 45-second interview explanation

“I built ShopSignal to show the full decision path behind an e-commerce recommender. I
used 15 million chronological H&M transactions and kept future behaviour out of training
features. A popularity model set the baseline and handles new users; implicit ALS then
retrieves 200 personalised candidates, and LightGBM LambdaMART re-ranks them to ten. On
the untouched test window, re-ranking improved NDCG@10 by about 6% and Recall@10 by about
12% over raw ALS, while MAP stayed effectively flat, which I report explicitly. I also
packaged the models behind single and batch FastAPI endpoints, added artifact loading,
Docker and 142 automated tests, and built GitHub Actions quality and deployment-simulation
workflows. The main unresolved issue is new-item coverage, so my next modelling step would
be hybrid content and collaborative retrieval.”

## STAR explanation

**Situation:** Retail recommendation requires both broad candidate coverage and precise
top-of-list ordering, while public transaction data has temporal drift and frequent new
products.

**Task:** Build and evaluate a reproducible recommendation pipeline that could be served
and released safely without overstating unconfigured cloud infrastructure.

**Action:** I created chronological train/validation/test windows, trained a popularity
baseline and confidence-weighted implicit ALS candidate model, constructed train-only
ranking features, and fitted a LambdaMART re-ranker. I added cold-start fallback, model
bundle loading, FastAPI single/batch inference, Docker health checks, automated tests, and
GitHub Actions release/deployment simulation.

**Result:** On 15 million transactions, ALS candidate Recall@200 was approximately 43%
above popularity on the tuning sample. The two-stage model improved untouched-test
NDCG@10 by approximately 6% and Recall@10 by approximately 12% over raw ALS. The project
finished with 142 passing tests; test MAP@10 remained at parity and Cloud Run was not
claimed as live.

## ATS keywords

Recommendation systems; recommender systems; machine learning engineering; implicit
feedback; collaborative filtering; alternating least squares (ALS); candidate generation;
learning to rank; LambdaMART; LightGBM; ranking metrics; NDCG; Recall; MAP; temporal
validation; data leakage prevention; cold start; feature engineering; Python; pandas;
scikit-learn; FastAPI; REST API; batch inference; model serving; model artifacts; Docker;
pytest; integration testing; smoke testing; GitHub Actions; CI/CD; MLOps; BigQuery; dbt;
Google Cloud Platform (GCP); Cloud Run; trunk-based development; reproducibility.
