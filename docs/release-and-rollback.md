# Release and Rollback Runbook

## Current release behaviour

On each push to `main`, GitHub Actions runs post-merge quality checks, creates a
`sha-<short-commit>` tag for a runner-local Docker build, starts the container, verifies
`/health`, and uploads build metadata.

The image is not pushed to a registry. Deployment jobs are simulations and do not create
Cloud Run revisions. Consequently, the rollback commands below are a future operational
runbook, not a record of tested production rollback.

## Intended immutable release flow

```text
merge to main
  → quality gates
  → build one SHA-tagged image
  → publish to Artifact Registry
  → approve and deploy the same image to staging
  → verify service health
  → approve and deploy the same image to production
  → monitor
```

The SHA tag should be immutable. Mutable aliases such as `staging` or `latest` may be
convenient pointers, but must not replace immutable release identity.

## Future rollback options

### Restore traffic to a known-good revision

```bash
gcloud run revisions list \
  --service=shopsignal-api \
  --region=australia-southeast1

gcloud run services update-traffic shopsignal-api \
  --to-revisions=KNOWN_GOOD_REVISION=100 \
  --region=australia-southeast1
```

### Redeploy a known-good immutable image

```bash
gh workflow run cd-deployment.yml \
  -f image_tag=sha-<known-good-sha> \
  -f environment=production
```

This option becomes valid only after registry publishing and real deployment steps are
enabled.

### Revert a defective source change

Create a focused revert branch, run the normal checks, and merge it through review. Do
not rewrite shared `main` history.

## Future deployment verification

After cloud activation, a successful command exit is not sufficient. Verify:

- the new Cloud Run revision is ready;
- `/health` returns the expected response from the deployed URL;
- error rate and latency remain inside agreed thresholds;
- the deployed image digest matches the approved release; and
- the previous known-good revision remains available during the observation window.

## Incident record

Any real rollback should record timeline, user impact, detection, root cause, resolution,
and assigned prevention work. There are currently no production incidents or rollback
results to report because no live environment exists.
