# Environments

ShopSignal has three deployment environments. Each environment has its own GitHub Environment with separate secrets and (for staging and production) manual approval requirements.

## Overview

| Environment | Purpose | Trigger | Approval | URL |
|-------------|---------|---------|----------|-----|
| `development` | Smoke tests, integration tests | Every push to `main` | None | localhost / PR preview |
| `staging` | Pre-production validation | After build RC passes | 1 reviewer | `staging-api.shopsignal.example.com` |
| `production` | Live traffic | Manual gate after staging | 1 reviewer | `api.shopsignal.example.com` |

## GitHub Environments

Each environment is configured under:  
`GitHub → Repository → Settings → Environments`

### development
- **Protection rules:** None (automatic)
- **Secrets:** None required (uses mock/localhost)
- **Purpose:** Verify Docker image starts, smoke tests pass

### staging
- **Protection rules:** Required reviewers (1)
- **Secrets:**
  - `GCP_PROJECT_ID` — staging GCP project
  - `WORKLOAD_IDENTITY_PROVIDER` — WIF pool for staging
  - `SERVICE_ACCOUNT_EMAIL` — staging SA
  - `CLOUD_RUN_SERVICE_NAME` — staging Cloud Run service
  - `GCP_REGION` — e.g. `australia-southeast1`
- **Wait timer:** 0 minutes (immediate after approval)

### production
- **Protection rules:** Required reviewers (1), wait timer 5 minutes
- **Secrets:** Same structure as staging but pointing to production project/SA
- **Deployment history:** Visible in GitHub Environments tab

## Environment Variables (non-secret)

These are set as GitHub Actions environment variables (not secrets):

| Variable | dev | staging | production |
|----------|-----|---------|------------|
| `APP_ENV` | `development` | `staging` | `production` |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `WARNING` |
| `NDCG_PROMOTION_THRESHOLD` | `0.30` | `0.35` | `0.35` |

## Secret Management Rules

- Secrets are **never** committed to Git
- Local development uses `.env` (gitignored)
- CI/CD uses GitHub Secrets (encrypted at rest, masked in logs)
- GCP authentication uses **Workload Identity Federation** (no long-lived keys)
- Service-account JSON keys are **explicitly forbidden** in this repository

## Workload Identity Federation (WIF)

Preferred authentication method for Cloud Run deployments.

```
GitHub Actions → Google WIF Pool → Service Account → Cloud Run
     │                                     │
   OIDC token              Impersonation (no JSON key)
```

Required setup (one-time, documented in `docs/manual-github-settings.md`):
1. Create WIF pool in GCP IAM
2. Create WIF provider (GitHub issuer)
3. Grant `roles/iam.workloadIdentityUser` to the GitHub repo
4. Add `roles/run.admin` + `roles/storage.admin` to the service account

## Rollback

See [`docs/release-and-rollback.md`](release-and-rollback.md) for rollback procedures per environment.
