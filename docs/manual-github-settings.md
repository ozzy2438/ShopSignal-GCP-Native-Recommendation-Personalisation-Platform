# Manual GitHub Settings

This document lists every GitHub setting that must be configured through the GitHub web interface — settings that cannot be set by code or scripts in this repository.

---

## Branch Protection — `main`

**Location:** `GitHub → Repository → Settings → Branches → Add rule`

**Branch name pattern:** `main`

### Rules to enable

| Setting | Value | Why |
|---------|-------|-----|
| Require a pull request before merging | ✅ | Prevents direct pushes to main |
| Required number of approvals before merging | `1` | Minimum peer review |
| Dismiss stale pull request approvals when new commits are pushed | ✅ | Forces re-review after updates |
| Require review from Code Owners | ✅ (optional) | Enforces CODEOWNERS |
| Require conversation resolution before merging | ✅ | No unresolved comments |
| Require status checks to pass before merging | ✅ | CI must be green |
| Require branches to be up to date before merging | ✅ | No stale code merges |
| Do not allow bypassing the above settings | ✅ | Applies to admins too |
| Allow force pushes | ❌ | Prevents history rewrite |
| Allow deletions | ❌ | Prevents accidental branch deletion |

### Required status checks (exact names — must match GitHub Actions job names)

After the CI workflow has run once, search for and add these checks:

```
validate-repository
lint
format-check
unit-tests
api-smoke-test
docker-build
```

---

## GitHub Environments

**Location:** `GitHub → Repository → Settings → Environments`

Create three environments:

### `development`
- Protection rules: None
- Secrets: None required

### `staging`
- Required reviewers: Add your GitHub username
- Secrets to add:
  - `GCP_PROJECT_ID`
  - `WORKLOAD_IDENTITY_PROVIDER`
  - `SERVICE_ACCOUNT_EMAIL`
  - `CLOUD_RUN_SERVICE_NAME`
  - `GCP_REGION`

### `production`
- Required reviewers: Add your GitHub username
- Wait timer: `5` minutes
- Secrets: Same structure as staging (different values)

---

## Repository Settings

**Location:** `GitHub → Repository → Settings → General`

| Setting | Recommended value |
|---------|------------------|
| Default branch | `main` |
| Allow squash merging | ✅ |
| Allow merge commits | ❌ |
| Allow rebase merging | ❌ |
| Automatically delete head branches | ✅ |

---

## Actions Permissions

**Location:** `GitHub → Repository → Settings → Actions → General`

| Setting | Recommended value |
|---------|------------------|
| Actions permissions | Allow all actions and reusable workflows |
| Fork pull request workflows | Require approval for first-time contributors |
| Workflow permissions | Read repository contents and packages |
| Allow GitHub Actions to create and approve pull requests | ✅ (required for automated PR creation) |

---

## Dependabot

Dependabot is configured via `.github/dependabot.yml` (already in this repository).  
After pushing that file, verify it is active:

**Location:** `GitHub → Repository → Insights → Dependency graph → Dependabot`

---

## Secrets Configured by CI/CD Team

These secrets must be added at the **repository level** for workflows that run on `main`:

| Secret name | Used by | How to obtain |
|-------------|---------|---------------|
| `GCP_PROJECT_ID` | deployment workflow | GCP Console → Project info |
| `WORKLOAD_IDENTITY_PROVIDER` | deployment workflow | GCP IAM → Workload Identity |
| `SERVICE_ACCOUNT_EMAIL` | deployment workflow | GCP IAM → Service Accounts |
| `ARTIFACT_REGISTRY_REPO` | build workflow | GCP Artifact Registry |

**To add a secret:**  
`GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret`

---

## Code Owners

The file `.github/CODEOWNERS` is already in this repository.  
To make CODEOWNERS effective, replace placeholder usernames with real GitHub usernames:

```
# Replace @platform-team, @data-engineering-team, @data-science-team
# with the actual GitHub usernames of your collaborators
```

---

## Security Advisories

**Location:** `GitHub → Repository → Security → Security advisories`

Enable:
- Dependency vulnerability alerts: ✅
- Dependabot security updates: ✅
- Secret scanning: ✅ (prevents accidental credential commits)

---

## Settings Verified as Automatically Applied

The following are handled by files already in this repository (no manual action needed):

| Item | File |
|------|------|
| Dependabot schedule | `.github/dependabot.yml` |
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` |
| Issue templates | `.github/ISSUE_TEMPLATE/` |
| CODEOWNERS routing | `.github/CODEOWNERS` |
| CI/CD workflows | `.github/workflows/` |
