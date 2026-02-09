# Quality Gate

> Definition of done, minimum tests, and rollback steps.

## Definition of Done

A feature/fix is "done" when:

1. ✅ **Local build passes** - `./scripts/preflight.ps1` exits with code 0
2. ✅ **CI passes** - GitHub Actions lint + build succeeds
3. ✅ **No TypeScript errors** - `npm run build` completes without type errors
4. ✅ **No lint errors** - `npm run lint` and `flake8` pass
5. ✅ **Tests pass** - `pytest` runs without failures
6. ✅ **Files are tracked** - `git ls-files` shows new files
7. ✅ **Documented** - LEARNINGS_LOG.md updated if lesson learned

---

## Minimum Tests

### Frontend
- Build must complete (`npm run build`)
- No TypeScript errors
- ESLint passes (warnings acceptable, errors not)

### Backend
- All existing tests pass (`pytest`)
- New routers should have at least one smoke test
- Imports must not fail (`python -c "from routers.my_router import router"`)

### Persona/Policy Gate (Phase 6, Blocking)
- Run regression gate:
  - `python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json`
- Required thresholds:
  - `pass_rate >= 0.95`
  - `adversarial_pass_rate >= 0.95`
  - `channel_isolation_pass_rate == 1.0`
- CI workflow:
  - `.github/workflows/persona-regression.yml` must pass for merge/release.

---

## Performance Budgets

| Metric | Budget |
|--------|--------|
| Frontend build time | < 60s locally |
| Backend test suite | < 30s |
| Next.js bundle size | Monitor via build output |
| API response time | < 2s for chat, < 500ms for CRUD |

---

## Rollback Steps

### Vercel (Frontend)
1. Go to Vercel Dashboard → Deployments
2. Find last working deployment
3. Click "..." → "Promote to Production"

### Render (Backend)
1. Go to Render Dashboard → Events
2. Find last successful deploy
3. Click "Rollback"

### Emergency Hotfix
```bash
# Revert last commit
git revert HEAD --no-edit
git push origin main

# Or reset to specific commit
git reset --hard <commit-hash>
git push origin main --force  # DANGEROUS - use only if necessary
```

---

## Pre-Commit Checklist

Before pushing any code:

- [ ] Ran `./scripts/preflight.ps1` (exit code 0)
- [ ] Checked `git status` for untracked files
- [ ] Verified new files with `git ls-files <path>`
- [ ] All imports include necessary hooks (useCallback, useEffect, etc.)
- [ ] No broad patterns added to `.gitignore`
- [ ] Migration tested in Supabase SQL Editor (if applicable)
