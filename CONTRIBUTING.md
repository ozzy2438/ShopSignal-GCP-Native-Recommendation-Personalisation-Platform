# Contributing to ShopSignal

Thank you for contributing. This guide explains the complete workflow from creating an issue to merging code.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Create a Branch](#2-create-a-branch)
3. [Branch Naming Conventions](#3-branch-naming-conventions)
4. [Commit Message Conventions](#4-commit-message-conventions)
5. [Open a Pull Request](#5-open-a-pull-request)
6. [How Review Works](#6-how-review-works)
7. [What "Request Changes" Means](#7-what-request-changes-means)
8. [Responding to Review Comments](#8-responding-to-review-comments)
9. [Updating a PR](#9-updating-a-pr)
10. [How CI Checks Rerun](#10-how-ci-checks-rerun)
11. [When a PR is Ready to Merge](#11-when-a-pr-is-ready-to-merge)
12. [How Squash Merging Works](#12-how-squash-merging-works)
13. [Local Development Setup](#13-local-development-setup)

---

## 1. Prerequisites

```bash
# Python 3.11+
python --version

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Mac / Linux

# Install dependencies
pip install -r requirements.txt

# Verify setup
make test
```

---

## 2. Create a Branch

Always branch from the latest `main`:

```bash
git checkout main
git pull origin main
git checkout -b <type>/<short-description>
```

Example:

```bash
git checkout -b feat/add-user-age-feature
```

---

## 3. Branch Naming Conventions

| Prefix | Use case | Example |
|--------|----------|---------|
| `feat/` | New feature | `feat/als-candidate-gen` |
| `fix/` | Bug fix | `fix/ndcg-zero-division` |
| `ci/` | CI/CD changes | `ci/add-coverage-badge` |
| `chore/` | Maintenance | `chore/update-fastapi` |
| `docs/` | Documentation | `docs/contributing-guide` |
| `refactor/` | Refactor only | `refactor/extract-metrics` |

Rules:
- Lowercase only
- Hyphens, not underscores
- Keep it short but meaningful
- No issue numbers in branch names (link via PR description instead)

---

## 4. Commit Message Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short description in present tense>

[optional body — explain WHY, not WHAT]

[optional footer: Closes #<issue-number>]
```

### Types

| Type | When to use |
|------|------------|
| `feat` | New feature visible to users or other developers |
| `fix` | Bug fix |
| `test` | Adding or correcting tests |
| `docs` | Documentation changes only |
| `ci` | Changes to GitHub Actions workflows |
| `chore` | Dependency updates, build config, maintenance |
| `refactor` | Code change that doesn't add features or fix bugs |
| `perf` | Performance improvement |

### Examples

```bash
feat(serve): add /version endpoint with build metadata
fix(metrics): handle empty relevant set in ndcg_at_k
test(serve): add unit tests for /recommend top_n validation
ci: cache pip dependencies in PR quality gates workflow
docs: update branching strategy with rebase guidance
chore: upgrade lightgbm from 4.2.0 to 4.3.0
```

### Rules

- Use the **imperative mood**: "add" not "added" or "adding"
- Keep the subject line under **72 characters**
- Do not end the subject line with a period
- Reference issues in the footer: `Closes #7`

---

## 5. Open a Pull Request

1. Push your branch:
   ```bash
   git push origin feat/my-feature
   ```

2. Open GitHub → you will see a yellow banner → click **Compare & pull request**

3. Complete the PR template — every section matters:
   - **Summary:** What does this PR do?
   - **Related issue:** Link to the issue it closes
   - **What changed:** List the files and changes
   - **Why:** Business or technical reason
   - **How tested:** Which tests cover the change
   - **Checklist:** Tick every item honestly

4. Set the base branch to `main`

5. Assign a reviewer (or request review)

6. Click **Create pull request**

---

## 6. How Review Works

Once your PR is open:

1. CI checks run automatically (lint, tests, Docker build)
2. A reviewer is notified
3. The reviewer reads the diff in **Files changed**
4. The reviewer leaves comments — either inline (on a specific line) or general
5. The reviewer submits one of:
   - **Comment** — observations, no decision
   - **Approve** ✅ — PR is ready to merge
   - **Request changes** ❌ — changes are required before merge

---

## 7. What "Request Changes" Means

When a reviewer selects **Request changes**:

- The PR is **blocked from merging** until the reviewer approves
- Their comments appear in the **Conversation** tab
- You must address every comment and re-request review

This is a normal part of the process — not a rejection. It means the reviewer wants to help you improve the code before it goes to main.

---

## 8. Responding to Review Comments

For each comment:

1. **Read it carefully** — understand what is being asked
2. If you agree: implement the change, then mark the conversation **Resolved**
3. If you disagree: reply explaining your reasoning and ask for clarification
4. If it's a question: answer it in a reply, then resolve if nothing needs to change

Do not silently resolve comments without addressing them — reviewers receive notifications.

---

## 9. Updating a PR

Push additional commits to the same branch:

```bash
# Make changes based on review
git add src/evaluate/metrics.py
git commit -m "fix: handle empty relevant set per reviewer feedback"
git push origin feat/my-feature
```

GitHub automatically adds the new commit to the existing PR.  
CI reruns on the new commit.

When all comments are addressed, click **Re-request review** (the circular arrow icon next to the reviewer's name).

---

## 10. How CI Checks Rerun

CI reruns automatically every time you push a new commit to the branch.

- The old CI run is **cancelled** automatically (concurrency is configured in the workflow)
- Only one CI run per PR branch is active at any time
- If a check was passing before your new commit, it runs again from scratch

To manually rerun a failed check without pushing new code:
1. Go to `Actions` tab → find the failed run
2. Click **Re-run failed jobs**

---

## 11. When a PR is Ready to Merge

Under the recommended branch-protection policy, all of the following must be true:

- [ ] All required CI checks are green ✅
- [ ] At least 1 reviewer has approved
- [ ] All review conversations are resolved
- [ ] The branch is up to date with `main` (rebase if needed)
- [ ] The PR checklist is complete

If `main` has moved ahead of your branch:

```bash
git fetch origin
git rebase origin/main
git push --force-with-lease origin feat/my-feature
```

---

## 12. How Squash Merging Works

ShopSignal's recommended merge strategy is **squash merging**.

When you merge a PR:
1. All commits on the branch are combined into **one single commit** on `main`
2. The commit message is the PR title (edit it before confirming)
3. The branch can be automatically deleted after merge when that repository setting is enabled

This keeps `main` history clean — each entry represents one complete, reviewed feature.

Example:

```
Before merge (your branch):
  abc1234 wip: first attempt
  def5678 fix lint
  ghi9012 add tests

After squash merge to main:
  jkl3456 feat(serve): add /version endpoint with build metadata
```

---

## 13. Local Development Setup

```bash
# Install everything
make install-dev

# Run linter
make lint

# Auto-format code
make format

# Run all tests
make test

# Run only unit tests
make test-unit

# Build Docker image
make docker-build

# Start API locally
uvicorn src.serve.app:app --reload --port 8080
# Open: http://localhost:8080/docs

# List all commands
make help
```
