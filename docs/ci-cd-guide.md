# CI/CD Guide — Step-by-Step Lifecycle Walkthrough

This guide traces one complete code change from idea to production deployment.

---

## The Full Path

```
Issue → Branch → Local change → Commit → Push → PR → Diff → CI checks →
Review → Updated commit → Approval → Squash merge → Build RC → Staging
approval → Production approval → Monitor → Rollback (if needed)
```

Each step below tells you what happens automatically, what requires a human, and exactly where to look in GitHub.

---

## Step 1 — Create a GitHub Issue

**What:** Document the intent before writing code.  
**Human action required:** Yes.

1. Go to `github.com/ozzy2438/<repo> → Issues → New issue`
2. Choose a template (Feature Request, Bug Report, etc.)
3. Fill in the form — the template guides you
4. Click **Submit new issue** — note the issue number (e.g. `#7`)

**Where to see it:** `Issues` tab → your new issue

---

## Step 2 — Create a Branch

**What:** Isolate your work from `main`.  
**Human action required:** Yes (you run the commands).

```bash
git checkout main
git pull origin main
git checkout -b feat/my-feature   # e.g. feat/version-endpoint-update
```

**Naming rule:** `<type>/<short-description>` (see [branching-strategy.md](branching-strategy.md))

---

## Step 3 — Make Local Changes and Commit

**What:** Write code, then commit with a Conventional Commit message.

```bash
# Make your changes
vim src/serve/app.py

# Run tests locally before committing
make lint
make test

# Stage and commit
git add src/serve/app.py tests/unit/test_serve.py
git commit -m "feat(serve): add build_date field to /version response"
```

**Commit message format:** `<type>(<scope>): <short description>`

---

## Step 4 — Push the Branch

```bash
git push origin feat/my-feature
```

**What happens automatically:** Nothing yet — no CI runs until you open a PR.

---

## Step 5 — Open a Pull Request

1. Go to `github.com/ozzy2438/<repo>`
2. GitHub shows a yellow banner: **"feat/my-feature had recent pushes"** → click **Compare & pull request**
3. The PR description template pre-fills — complete every section
4. Set the **base branch** to `main`
5. Link the issue: type `Closes #7` in the description
6. Click **Create pull request**

**Where to see it:** `Pull requests` tab

---

## Step 6 — Observe the Code Diff

1. Open your PR
2. Click the **Files changed** tab
3. Green lines = additions, red lines = deletions
4. You can comment on any specific line by clicking the `+` icon

**What to look for:**
- Is the change focused and minimal?
- Are new tests included alongside new code?
- Are there any accidental changes (whitespace, unrelated files)?

---

## Step 7 — Automated CI Checks Run

**What happens automatically (within ~1–2 minutes):**

The workflow `CI — Pull Request Quality Gates` starts automatically.

```
GitHub Actions jobs (run in parallel/series):
  ┌─ validate-repository ─── checks folder structure and gitignore
  ├─ lint ──────────────────── ruff check src tests pipelines
  ├─ format-check ─────────── ruff format --check
  └─ after lint+format passes:
       ├─ unit-tests ──────── pytest tests/unit/
       ├─ api-smoke-test ──── pytest tests/smoke/
       └─ docker-build ────── docker build . (no push)
```

**Where to see it:**
- In your PR → scroll to the bottom → **Checks** section
- Or: `Actions` tab → click the workflow run

**Status indicators:**

| Icon | Meaning |
|------|---------|
| 🟡 Yellow circle | Running |
| ✅ Green check | Passed |
| ❌ Red X | Failed — click to see logs |
| ⏭️ Grey circle | Skipped (dependency not met) |
| 🚫 Cancelled | Cancelled (e.g. a newer push superseded this run) |

---

## Step 8 — Fix a Failed Check

If a check fails:

1. Click the red ❌ → **Details** → read the log
2. Fix the issue locally
3. Commit the fix:
   ```bash
   git add .
   git commit -m "fix: correct ruff lint error in metrics.py"
   git push origin feat/my-feature
   ```
4. **The CI workflow reruns automatically** — you do not need to manually trigger it

**Concurrency:** When you push a new commit, the old CI run is cancelled automatically (configured with `concurrency` in the workflow file).

---

## Step 9 — Human Code Review

**What:** A collaborator (or you, as a second perspective) reviews the diff.  
**Human action required:** Yes — the merge is blocked until there is at least 1 approval.

**Reviewer steps:**
1. Open the PR → **Files changed**
2. Read every changed line — focus on correctness and test coverage
3. Leave inline comments by clicking `+` next to a line
4. When done: **Review changes** → choose:
   - **Comment** — observations, no block
   - **Approve** — LGTM, ready to merge
   - **Request changes** — must be addressed before merge

**For the author:**
- Respond to every comment (reply or resolve)
- Push additional commits if changes are needed
- Re-request review when ready

---

## Step 10 — Merge Requirements Check

Before the **Merge** button becomes green, all of the following must be true:

- [ ] All required CI checks are ✅ green
- [ ] At least 1 reviewer has approved
- [ ] All review conversations are resolved
- [ ] The branch is up to date with `main`

If any condition is not met, the Merge button is disabled or shows a warning.

---

## Step 11 — Squash Merge

1. Click **Squash and merge** (the dropdown on the Merge button)
2. Edit the commit message if needed — it becomes the single commit on `main`
3. Click **Confirm squash and merge**
4. GitHub asks to delete the branch — click **Delete branch**

**What happens:** All your commits are squashed into one clean commit on `main`.

---

## Step 12 — Build Release Candidate (Automatic)

After the merge, the workflow `CD — Build Release Candidate` runs automatically.

**What it does:**
1. Checks out the merged code
2. Runs quality checks again
3. Builds the Docker image
4. Tags it with the commit SHA: `sha-a1b2c3d`
5. Generates a build summary in GitHub Actions
6. Uploads a build metadata artifact

**Where to see it:** `Actions` tab → `CD — Build Release Candidate`

**Note:** This workflow does NOT deploy anywhere — it only confirms the build is healthy.

---

## Step 13 — Deploy to Staging (Manual Approval)

1. Go to `Actions` → `CD — Deployment`
2. Click on the latest run → find the `deploy-staging` job
3. It shows: **"Waiting for review"** with a yellow shield 🛡️
4. Click **Review deployments** → tick `staging` → click **Approve and deploy**

**What happens automatically after approval:**
- Cloud Run revision is updated with the new image
- Health check is verified
- Deployment is recorded in GitHub Environments history

**Where to see deployment history:** `Settings → Environments → staging → Deployment history`

---

## Step 14 — Deploy to Production (Manual Approval + Wait)

Same as staging but:
- Requires a separate approval (can be you or a second person)
- Has a 5-minute wait timer (deliberate pause to catch last-minute problems)
- Uses production secrets (different GCP project / service account)

---

## Step 15 — Monitor

After production deployment:

- **Cloud Run metrics:** GCP Console → Cloud Run → shopsignal-api → Metrics
- **Error rate:** look for 5xx spikes in the first 15 minutes
- **Health endpoint:** `curl https://api.shopsignal.example.com/health`
- **GitHub Actions:** the deployment job shows the Cloud Run URL

---

## Step 16 — Rollback (If Needed)

If something goes wrong, see [`docs/release-and-rollback.md`](release-and-rollback.md).

The fastest path is Cloud Run traffic split — no code change needed:

```bash
gcloud run services update-traffic shopsignal-api \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region=australia-southeast1
```

---

## How to Download Build Artifacts

1. `Actions` tab → click any workflow run
2. Scroll to the bottom of the run summary page
3. Find the **Artifacts** section
4. Click the artifact name to download the `.zip`

---

## How to Rerun a Failed Job

1. `Actions` tab → failed workflow run
2. Click **Re-run all jobs** (top right) — or click the failed job → **Re-run job**
3. Jobs that already passed do not need to rerun (GitHub Actions caches the result)

---

## Status Check Glossary

| Status | Meaning | What to do |
|--------|---------|-----------|
| ✅ Green check | Passed | Nothing |
| ❌ Red X | Failed | Click → Details → read log → fix → push |
| 🟡 Yellow circle | Running | Wait |
| ⏭️ Skipped | Not applicable | Check workflow conditions |
| 🚫 Cancelled | Superseded by newer push | Push was updated — new run started |
| ❓ Pending | Queued, waiting for runner | Wait — usually < 1 minute |
