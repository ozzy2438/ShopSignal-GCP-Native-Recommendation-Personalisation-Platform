# CI/CD Guide and Automation Boundary

ShopSignal uses trunk-based development with pull-request quality gates. The repository
demonstrates a complete build-and-promotion shape while keeping cloud writes disabled
until credentials and cost approval exist.

## What runs automatically

### Pull requests to `main`

`.github/workflows/ci-pr-quality-gates.yml` runs when a PR is opened, updated, or reopened.

| Job | Verified action |
|---|---|
| Repository validation | Checks required files and obvious credential files |
| Ruff lint | `ruff check src tests pipelines` |
| Ruff formatting | `ruff format --check src tests pipelines` |
| Unit tests | Runs `tests/unit/` with coverage artifacts |
| API smoke tests | Runs `tests/smoke/` through FastAPI `TestClient` |
| Docker build | Builds the image without pushing it |
| Container verification | Starts the image and checks `/health` |

The Docker job does not require model artifacts. With no `SHOPSIGNAL_MODEL_DIR`, the API
starts in deterministic mock mode so infrastructure checks remain isolated from large
training files.

### Pushes to `main`

`.github/workflows/cd-build-release-candidate.yml` reruns lint, formatting, unit/smoke
tests, then:

1. derives `sha-<short-commit>` build metadata;
2. builds and loads a Docker image inside the GitHub runner;
3. starts the container and probes `/health`; and
4. uploads JSON build metadata as a workflow artifact.

The image receives a local SHA tag for traceability, but `push: false` is configured.
Nothing is published to Artifact Registry and the runner-local image disappears after
the job.

## What is simulated

### Deployment workflow

`.github/workflows/cd-deployment.yml` contains staging and production jobs associated with
GitHub Environments. The active steps only print clearly labelled simulation summaries.
Authentication, registry access, `deploy-cloudrun`, and remote health checks are commented
reference steps.

Therefore:

- example `shopsignal.example.com` URLs are placeholders, not reachable services;
- environment approval records do not prove a Cloud Run revision was created;
- rollback commands are operational runbook examples, not evidence of a prior deployment;
- no staging or production traffic is claimed.

Activation requires a GCP project, Artifact Registry, Workload Identity Federation,
service accounts/roles, repository secrets, environment protection rules, and explicit
cost approval.

### Retraining and promotion workflow

`.github/workflows/mlops-retrain.yml` is manual-only; its weekly cron is commented out.
The current jobs demonstrate sequencing and artifact/summary handling, but validation,
training, metrics, and promotion use placeholder values. `pipelines/retrain.py` is also a
stub and does not call the validated ALS/LightGBM evidence path.

Do not interpret its mock NDCG value as a model result. Verified model results live only
in `docs/als_tuning_results.md` and `docs/lightgbm_ranker_results.md`.

## Development workflow

```text
issue or scoped task
  → short-lived branch
  → local lint/tests
  → Conventional Commit
  → pull request
  → automated quality gates
  → human review
  → squash merge
  → release-candidate build and health check
```

Recommended local pre-push commands:

```bash
ruff check src tests pipelines
ruff format --check src tests pipelines
pytest tests/ -v
docker build -t shopsignal-api:local .
```

## Failure diagnosis

- **Ruff failure:** run the same command locally and correct only the reported files.
- **Test failure:** reproduce the failing node ID with `pytest <node-id> -v`.
- **Docker build failure:** rebuild locally without cache if a dependency layer is suspect.
- **Health failure:** run the image, inspect `docker logs`, and probe `/health` directly.
- **Cancelled run:** a newer push superseded the run through workflow concurrency.

## Future activation checklist

The following are optional future work, not current repository claims:

1. provision BigQuery datasets and validate dbt sources/models;
2. replace the upload and retraining stubs with the implemented data/model modules;
3. publish immutable SHA-tagged images to Artifact Registry;
4. configure Workload Identity Federation with least-privilege roles;
5. replace example URLs and enable real Cloud Run deployment/health checks;
6. add artifact lineage, monitoring, alerting, and tested rollback automation;
7. enable scheduling only after runtime, quota, and cost controls are approved.

Manual repository/GCP configuration is described in
[`manual-github-settings.md`](manual-github-settings.md). The current honest deployment
status is also summarised in [`environments.md`](environments.md).
