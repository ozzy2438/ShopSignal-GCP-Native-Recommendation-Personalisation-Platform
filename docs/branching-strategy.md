# Branching Strategy — Trunk-Based Development

ShopSignal uses **trunk-based development** with short-lived feature branches.

## Core Rule

`main` is always in a deployable state.  
Every change reaches `main` through a Pull Request with at least one CI check passing and one human approval.

## Branch Naming

| Pattern | When to use | Example |
|---------|-------------|---------|
| `feat/<scope>` | New feature | `feat/als-candidate-gen` |
| `fix/<scope>` | Bug fix | `fix/ndcg-calculation-edge-case` |
| `ci/<scope>` | CI/CD changes | `ci/add-docker-build-check` |
| `chore/<scope>` | Maintenance | `chore/update-dependencies` |
| `docs/<scope>` | Documentation | `docs/api-usage-guide` |
| `refactor/<scope>` | Code cleanup | `refactor/extract-feature-pipeline` |
| `demo/<scope>` | Demonstration | `demo/version-endpoint-update` |

## Lifecycle

```
main
 │
 ├── feat/my-feature  ← create from latest main
 │       │
 │       ├── commit: feat: add X
 │       ├── commit: test: add tests for X
 │       └── commit: docs: update README for X
 │
 └── [PR opened → CI → review → approve → squash merge → delete branch]
```

## Branch Age

- Target lifetime: **< 1 day**
- Maximum: **3 days** before staleness review
- Stale branches are updated via `git rebase origin/main`

## Commit Message Convention (Conventional Commits)

```
<type>(<optional scope>): <short description>

[optional body]

[optional footer: Closes #<issue-number>]
```

### Types

| Type | When |
|------|------|
| `feat` | New functionality |
| `fix` | Bug fix |
| `test` | Adding or updating tests |
| `docs` | Documentation only |
| `ci` | CI/CD workflow changes |
| `chore` | Build, dependencies, configuration |
| `refactor` | Code restructuring (no behaviour change) |
| `perf` | Performance improvement |

### Examples

```bash
feat(serve): add /version endpoint returning app metadata
fix(metrics): correct ndcg edge case when relevant set is empty
test(serve): add unit tests for /recommend endpoint
ci: add docker build validation job to PR workflow
chore: bump lightgbm to 4.3.0
docs: add architecture diagram to README
```

## Merge Strategy

- **Always squash merge** PRs into `main`
- This keeps `main` history clean: one meaningful commit per PR
- The squash commit message is the PR title

## Protected Branches

Only `main` has branch protection enabled.  
Feature branches are personal — push force is allowed while the PR is open.
