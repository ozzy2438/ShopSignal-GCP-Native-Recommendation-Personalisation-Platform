# GitHub and Future GCP Settings

This is a recommended configuration checklist. It does not claim that repository settings,
GCP resources, secrets, or live environments have already been configured.

## Repository settings

Recommended `main` protection:

- require a pull request and one approval;
- dismiss stale approvals after new commits;
- require conversation resolution;
- require the PR quality-gate checks;
- disallow force pushes and branch deletion; and
- automatically delete merged head branches.

Enable squash merging and use the PR title as a Conventional Commit-style squash message.

## GitHub Environments

If real deployment is approved, create `staging` and `production` environments. Require a
reviewer for both and consider a production wait timer. Until Cloud Run exists, do not set
placeholder URLs as evidence of deployed environments.

Suggested environment secrets/variables:

- `GCP_PROJECT_ID`
- `WORKLOAD_IDENTITY_PROVIDER`
- `SERVICE_ACCOUNT_EMAIL`
- `CLOUD_RUN_SERVICE_NAME`
- `GCP_REGION`

Prefer environment-scoped values so staging and production cannot accidentally share
targets.

## GCP prerequisites

Before enabling the commented workflow steps:

1. approve a project and cost budget;
2. create Artifact Registry and Cloud Run resources;
3. configure GitHub OIDC through Workload Identity Federation;
4. grant only the registry/deployment permissions required by each environment;
5. verify image-digest and revision rollback procedures; and
6. replace example domains with real outputs from the deployment action.

Do not create or commit service-account JSON keys.

## CODEOWNERS and security

Review `.github/CODEOWNERS` before requiring code-owner approval; team aliases must map to
real users/teams. Enable dependency alerts, Dependabot security updates, and secret
scanning where repository settings permit.

## Recruiter-facing GitHub presentation

These changes affect repository metadata and should be applied manually by the owner,
not silently from this documentation branch.

**Suggested description**

> Two-stage retail recommender: implicit ALS retrieval, LightGBM LambdaMART ranking,
> FastAPI/Docker serving, temporal evaluation, and GCP-oriented MLOps.

**Suggested topics**

`recommendation-system`, `machine-learning`, `learning-to-rank`, `lightgbm`,
`implicit-feedback`, `fastapi`, `docker`, `github-actions`, `mlops`, `bigquery`, `dbt`,
`gcp`

**Suggested About text**

> Leakage-safe two-stage recommendation platform evaluated on 15M retail transactions;
> packaged with FastAPI, Docker, and tested CI/CD simulation.

**Suggested pinned-repository summary**

> Built and evaluated an ALS → LambdaMART recommender on 15M H&M transactions, improving
> test NDCG@10 by ~6% and Recall@10 by ~12% over raw ALS, with cold-start fallback and
> containerised API serving.

Avoid metadata that says the service is live, production-deployed, powered by Vertex AI,
or has generated commercial/online uplift.

## Licence metadata

`pyproject.toml` currently declares MIT, but the repository does not contain a licence
file. Confirm code/data ownership and the intended terms before adding `LICENSE`; do not
present the project as licensed until that legal choice is made explicitly.
