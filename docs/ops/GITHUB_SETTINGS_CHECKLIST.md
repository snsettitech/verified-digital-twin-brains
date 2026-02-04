# GitHub Settings Checklist: Two-Agent Workflow

Complete this checklist to enable the controlled two-agent workflow (Codex + Antigravity).

## Branch Protection for `main`

**Location:** Settings → Branches → main → Edit branch protection rule

### Required Checks
- [ ] Require pull request before merging
  - [ ] Require approvals: **1**
  - [ ] Dismiss stale pull request approvals when new commits are pushed: **ON**
  - [ ] Require status checks to pass before merging: **ON**
    - Select these checks:
      - [ ] `tests` (or your test runner name)
      - [ ] `lint` (or your linter name)
      - [ ] `typecheck` (TypeScript or Pyright)
  - [ ] Require branches to be up to date before merging: **ON**
  - [ ] Restrict who can push to matching branches: Leave blank (unless you want extra restrictions)
  - [ ] Allow force pushes: **OFF**
  - [ ] Allow deletions: **OFF**

## Security & Secret Management

**Location:** Settings → Code security and analysis

### Required
- [ ] Secret scanning: **ON**
  - Alerts you and repo admins when secrets are detected
- [ ] Push protection: **ON**
  - Blocks commits containing detected secrets
- [ ] Dependabot alerts: **ON**
  - Notifies you of vulnerable dependencies
  - (Optional) Enable Dependabot security updates for auto-patching

## Code Owners (Optional but Recommended)

**Location:** Create file `.github/CODEOWNERS`

Use this to require review from specific people on sensitive files:

```
# Multi-tenancy and auth — require human review
/backend/modules/_core/ @your-github-handle
/backend/modules/auth_guard.py @your-github-handle
/backend/modules/observability.py @your-github-handle
/backend/routers/ @your-github-handle
/frontend/middleware.ts @your-github-handle

# Database and migrations
/backend/database/migrations/ @your-github-handle
```

## PR Labels (Optional)

**Location:** Settings → Labels

Add these labels to PRs for easier tracking:

- `agent:codex` — Codex implementation
- `agent:antigravity` — Antigravity fixes/tests
- `area:backend` — Backend changes
- `area:frontend` — Frontend changes
- `area:infra` — Infrastructure/CI changes
- `risk:high` — Breaking or high-risk change
- `risk:medium` — Moderate risk
- `risk:low` — Low risk
- `migration:required` — Database migration included

## Status Checks Configuration

**Location:** Settings → Branches → main → Status checks

Ensure these pass before merge:

- [ ] Unit tests
- [ ] Linting (flake8, eslint)
- [ ] Type checking (Pyright, TypeScript)
- [ ] Any custom checks (security scan, performance test, etc.)

## Environment Protection (Optional)

**Location:** Settings → Environments

If you deploy staging/production from GitHub Actions:

- [ ] Create environment: `staging`
- [ ] Create environment: `production`
- [ ] Enable environment protection rules (require reviews before deployment to production)

## Verification

Run this to check if your local repo respects the rules:

```bash
# Try to force-push (should fail)
git push -f origin main
# → Error: force push denied

# Try to commit directly without PR (should fail if using GitHub's web UI protection)
# → GitHub UI blocks direct commits to main
```

## Automation: GitHub Actions CI

Ensure `.github/workflows/lint.yml` (or similar) runs on every PR:

- Tests
- Lint
- Typecheck

This is your "gating" mechanism. If CI is flaky, agents will struggle with merge confidence.

---

**Questions?** Refer to CONTRIBUTING.md for the full playbook.
