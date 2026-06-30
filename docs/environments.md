# Environments and Deployment Status

Only local/test execution is active. `staging` and `production` are workflow targets that
demonstrate approval gates; they are not provisioned Cloud Run environments.

| Target | Current behaviour | Live URL |
|---|---|---|
| Local / CI | FastAPI, tests, Docker build, and `/health` verification | `localhost:8080` while running |
| Staging | GitHub Actions deployment simulation | None |
| Production | GitHub Actions deployment simulation | None |

The URLs in `.github/workflows/cd-deployment.yml` use the reserved example domain and are
placeholders only.

## Local and CI configuration

- Local development copies `.env.example` to the gitignored `.env` file.
- CI needs no cloud secret because the API can boot without a model bundle.
- `SHOPSIGNAL_MODEL_DIR` enables real local model loading when a complete gitignored
  bundle is available.
- Docker sets `APP_ENV=production` by default as runtime configuration; this label does
  not mean that the image has been deployed.

## Prepared GitHub Environments

The deployment workflow references `staging` and `production` GitHub Environments so that
reviewer gates can be configured before any future cloud activation. Suggested protection
rules and secret names are documented in `manual-github-settings.md`.

Required future values include:

- `GCP_PROJECT_ID`
- `WORKLOAD_IDENTITY_PROVIDER`
- `SERVICE_ACCOUNT_EMAIL`
- `CLOUD_RUN_SERVICE_NAME`
- `GCP_REGION`

They have not been supplied or validated as part of the local project evidence.

## Intended authentication design

If cloud deployment is activated, GitHub Actions should exchange its OIDC identity through
Google Workload Identity Federation and impersonate a narrowly scoped service account.
No service-account JSON key should be committed or stored as a long-lived repository
secret.

```text
GitHub Actions OIDC → Workload Identity Federation → service account → Cloud Run
```

## Activation gate

Real staging/production use requires all of the following:

1. explicit GCP cost approval;
2. provisioned Artifact Registry and Cloud Run services;
3. configured keyless identity and least-privilege IAM;
4. immutable image publishing;
5. real service URLs and post-deployment health checks;
6. monitoring and tested rollback; and
7. removal of simulation-only workflow steps through a reviewed change.

Until then, documentation and CV material must describe the application as
**Cloud Run-ready with simulated deployment**, never live or production-deployed.
