# Contributing: Two-Agent Workflow (Codex + Antigravity)

This repo supports a controlled two-agent workflow to increase parallel velocity without increasing regressions.

## Non-negotiables
- No direct pushes to `main`
- All changes go through PRs
- CI must be green before merge
- At least one human review required before merge

## Roles
- **Codex**: feature implementation, contained refactors, implementation PRs
- **Antigravity**: reproduction, tests, integration verification, minimal fixes PRs

## Branching
- Branch per agent per task:
  - `codex/feat-...`
  - `antigravity/fix-...`
  - `antigravity/test-...`
- Keep branches short-lived (prefer under 3 days)

## PR Rules
- Keep PRs small and single-purpose
- PR must include: scope, repro steps, evidence, risk notes
- If a migration is included: include reversible SQL and verification steps
- Use the PR template in `.github/pull_request_template.md` for consistency

## Conflict Avoidance

**Golden Rule: Only one agent may touch contract surfaces at a time.** Contract surfaces include:
- API routes (`/routers/`)
- Shared schemas and types
- API client contracts (`/lib/api/`)
- Database models and migrations
- Auth and tenancy layers

If unavoidable, use sequential PRs and add a design note in the PR description.

Other core files (avoid concurrent edits):
- `modules/_core/`
- `modules/clients.py` (singleton client management)
- `modules/auth_guard.py` (auth patterns)
- `frontend/lib/` (auth context)

If both agents must touch the same file:
- Write a short design note in the PR
- Prefer sequential PRs
- Coordinate in PR comments or open an issue

## Canonical Contracts
- Any API or schema shape change must update `docs/CONTRACTS.md` (single source of truth)
- Keep `API_CONTRACTS.md` and this file in sync for routing/security changes

## Security and Hygiene
- Never commit secrets or `.env`
- Do not loosen CORS, auth checks, or RLS without explicit justification in the PR
- Enable secret scanning and push protection in GitHub settings (see below)
- Always verify multi-tenant isolation: all queries filtered by `tenant_id` or `twin_id`
- Refer to `.github/copilot-instructions.md` and `AGENT_MANUAL.md` for security patterns

## Suggested Merge Pattern
1. **Codex** opens implementation PR on `codex/feat-xyz`
2. **Antigravity** opens tests-only PR on `antigravity/test-xyz` (referencing Codex PR)
3. Merge implementation PR, then merge tests PR (or fold tests into the first PR if small)

## GitHub Settings: Enable These Now

These settings make the workflow actually work. Configure in **Settings → Branches → main → Branch protection rule**.

### Required
- ✅ Require pull request before merging
  - Require approvals: `1`
  - Dismiss stale approvals on new commits: `ON`
  - Require status checks to pass: `ON` (tests, lint, typecheck)
  - Require branch to be up to date before merging: `ON`
  - Restrict force pushes: `ON`
  - Restrict deletions: `ON`

### Security
- ✅ Secret scanning: `ON` (Settings → Security → Secret scanning)
- ✅ Secret scanning push protection: `ON` (prevents commits with leaked secrets)
- ✅ Dependabot alerts: `ON` (Settings → Code security → Dependabot)

### Optional but Recommended
- **CODEOWNERS** for core-risk files (see example below)
- Label convention: `agent:codex`, `agent:antigravity`, `area:frontend`, `area:backend`, `risk:high`

### CODEOWNERS Example (add to `.github/CODEOWNERS`)
```
# Core multi-tenant and auth — require human review
/backend/modules/_core/ @your-github-handle
/backend/modules/auth_guard.py @your-github-handle
/backend/modules/observability.py @your-github-handle
/backend/routers/ @your-github-handle
/frontend/middleware.ts @your-github-handle
```

## What To Do Next
1. **Enable branch protection** on `main` (copy the settings above)
2. **Enable secret scanning** and push protection
3. **Add labels** to issues/PRs for tracking agent and area
4. **Share this playbook** with the team — consistency is the win

## When NOT to Use This Pattern
- Large core refactors touching foundational modules
- When CI is down or flaky (fix CI first)

## If Things Go Wrong
- **Merge conflict**: Prefer reverting the PR and re-submitting smaller changes
- **Regression detected**: Tag it `regression` and notify the other agent; rollback via `git revert <sha>`
- **Unclear ownership**: Check CONTRIBUTING and CODEOWNERS; add a comment in the PR to clarify

---

## Fast Sanity Checklist (Do This Now)

- [ ] PR template is in `.github/pull_request_template.md` (lowercase)
- [ ] `main` is protected with required checks + 1 approval
- [ ] Secret scanning + push protection enabled
- [ ] CODEOWNERS created for auth, tenancy, routers, contracts
- [ ] Merge strategy set to squash merging
- [ ] CI includes backend tests, frontend typecheck, and lint
- [ ] One agent per contract surface (routers, schemas, API clients, migrations)

---

**Thank you for keeping PRs small, evidence-based, and focused.** Small disciplined steps prevent big regressions.
