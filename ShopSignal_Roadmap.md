# ShopSignal Roadmap and Delivery Status

This document records what exists now and what remains optional future work. It replaces
the original day-by-day build plan, which no longer reflected the implemented project.

## Delivered and locally validated

- H&M local CSV loading and schema/value validation
- leakage-safe temporal train/validation/test splitting
- train-only popularity baseline and cold-start fallback
- confidence-weighted implicit ALS candidate generation
- LightGBM LambdaMART top-10 re-ranking
- NDCG, Recall, MAP, hit-rate, and cold-start diagnostics
- train-only feature construction and grouped ranking datasets
- model component/bundle persistence and metadata
- FastAPI `/health`, `/version`, `/recommend`, and `/recommend/batch`
- deterministic mock mode when large artifacts are unavailable
- multi-stage non-root Docker packaging and health checks
- unit, integration, and smoke tests
- GitHub Actions PR quality gates and post-merge release-candidate builds
- BigQuery-oriented dbt staging and mart SQL
- documented deployment simulation and future rollback procedures

## Validated evidence snapshot

The final modelling run used 15 million transactions from 2019-09-19 to 2020-09-22.

| Evidence | Result |
|---|---:|
| Split rows | 11,613,037 train / 1,821,718 validation / 1,565,245 test |
| ALS matrix | 899,083 users × 62,078 items |
| ALS validation/test Recall@200 | 0.0843 / 0.0578 |
| ALS lift over popularity candidate baseline | ~43% Recall@200 on tuning sample |
| Two-stage test NDCG@10 | 0.0094 (~6% over raw ALS) |
| Two-stage test Recall@10 | 0.0124 (~12% over raw ALS) |
| Two-stage test MAP@10 | 0.0046 (parity, marginally below raw ALS 0.0047) |
| Full ranker evaluation resources | ~1 h 56 min / ~6.3 GB peak RAM |
| Automated tests after serving integration | 142 passed |

See `docs/als_tuning_results.md` and `docs/lightgbm_ranker_results.md` for the complete
offline protocol and results.

## Prepared but not activated

- BigQuery materialisation of the dbt models
- Artifact Registry publication
- Workload Identity Federation credentials and IAM bindings
- real staging and production Cloud Run services
- remote deployment health checks and monitoring
- scheduled retraining with real data/model artifacts

The active deployment workflow is a simulation. The retraining workflow is manual and
uses placeholder values. Neither is evidence of a live production platform.

## Recommended next steps

### 1. Close the new-item retrieval gap

Test-period cold-start items reached 26.4%, and ALS has no factor for unseen products.
Add a content-based candidate generator using available article metadata, then combine
its candidates with ALS before re-ranking. Evaluate the hybrid against the same untouched
temporal protocol.

### 2. Connect the cloud data path

Provision a controlled GCP project, implement the BigQuery upload interface, add dbt
source/schema tests, parameterise feature cutoffs, and compare cloud-generated features
with the validated local pandas path.

### 3. Build real retraining orchestration

Replace mock workflow stages with explicit calls to versioned training/evaluation code.
Store artifact lineage, configuration, dataset cutoffs, metrics, and promotion decisions.
Enable scheduling only after quota and cost controls are approved.

### 4. Activate deployment safely

Publish one immutable SHA-tagged image, configure keyless identity, deploy the same digest
through staging and production approvals, and add real health/latency/error monitoring.
Test rollback before accepting traffic.

### 5. Add online validation only when traffic exists

Define recommendation coverage, latency, click-through, conversion, and guardrail metrics.
No online uplift should be claimed until a properly designed experiment has run.

## Explicitly out of scope

Vertex AI and semantic search are not part of the implemented architecture. They are not
required to demonstrate the project's core recommendation and MLOps decisions. Future
extensions should be selected only when they address a measured limitation, not to expand
the technology list.
