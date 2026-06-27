# Release and Rollback

## Release Process

Every release follows this path:

```
PR merged to main
    ↓
CD — Build Release Candidate (automatic)
    • Runs quality checks
    • Builds Docker image
    • Tags image with commit SHA (e.g. sha-a1b2c3d)
    • Uploads build summary as GitHub Actions artifact
    ↓
Deploy to Staging (requires manual approval)
    • Reviewer clicks "Approve and deploy" in GitHub Environments
    • Cloud Run revision is updated
    • Health check is verified
    ↓
Deploy to Production (requires manual approval + 5 min wait)
    • Second reviewer approves
    • Cloud Run revision updated
    • Same SHA image deployed (no rebuild)
    • Deployment recorded in GitHub Environments history
```

## Image Tagging Strategy

| Tag | When created | Example |
|-----|-------------|---------|
| `sha-<git-sha>` | Every merge to main | `sha-a1b2c3d` |
| `staging` | Deployed to staging | `staging` |
| `latest` | Deployed to production | `latest` |

The SHA tag is **immutable** — it always refers to the exact code that was tested.  
Mutable tags (`staging`, `latest`) are convenience aliases.

## Rollback Procedures

### Option 1 — Cloud Run Traffic Split (fastest, < 1 minute)

```bash
# List recent revisions
gcloud run revisions list \
  --service=shopsignal-api \
  --region=australia-southeast1

# Roll back to previous revision
gcloud run services update-traffic shopsignal-api \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=australia-southeast1
```

### Option 2 — Redeploy Previous Docker Image (< 5 minutes)

```bash
# Identify the last known-good SHA from GitHub Actions
# Then re-deploy that image via the deployment workflow

# Trigger the deployment workflow with the previous SHA tag
gh workflow run cd-deployment.yml \
  -f image_tag=sha-<previous-sha> \
  -f environment=production
```

### Option 3 — Revert Git Commit and Re-merge (< 15 minutes)

```bash
# Create a revert branch
git checkout main
git pull
git revert <bad-commit-sha> --no-edit
git checkout -b fix/revert-bad-change
git push origin fix/revert-bad-change

# Open a PR, get it reviewed and merged
# The normal CI/CD pipeline will deploy the revert
```

## Rollback Decision Criteria

| Situation | Recommended Action |
|-----------|-------------------|
| High error rate (>5%) in first 5 minutes | Option 1 — immediate traffic split |
| NDCG regression detected in monitoring | Option 2 — redeploy previous model image |
| Security vulnerability discovered | Option 3 — revert + patch + re-merge |
| Partial outage, root cause unknown | Option 1, then investigate, then Option 3 |

## Health Verification After Deployment

After each Cloud Run deployment:

```bash
# Check revision health
gcloud run revisions describe <revision-name> \
  --region=australia-southeast1 \
  --format="get(status.conditions)"

# Manual health probe
curl -s https://api.shopsignal.example.com/health
# Expected: {"status":"ok","env":"production"}

# Check recent error rates
# GCP Console → Cloud Run → shopsignal-api → Metrics → Request Count (5xx)
```

## Post-Mortem Template

After any rollback, write a brief post-mortem:

1. **What happened:** Brief timeline of the incident
2. **Root cause:** What broke and why
3. **Detection:** How was the problem discovered
4. **Resolution:** What steps resolved it and how long it took
5. **Prevention:** What will prevent this from happening again
6. **Action items:** Concrete tasks with owners and due dates

Post-mortems are stored in `docs/post-mortems/YYYY-MM-DD-<title>.md`.
