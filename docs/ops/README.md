# Compounding Engineering System - Quick Reference

## Core Documents

| Document | When To Use |
|----------|-------------|
| **TROUBLESHOOTING_METHODOLOGY.md** | Any time debugging something |
| **AUTH_TROUBLESHOOTING.md** | 401/403 errors, JWT issues |
| **PRODUCTION_RESEARCH_CANARY_RUNBOOK.md** | Post-deploy production smoke test for onboarding + deep research |
| **AGENT_BRIEF.md** | Project overview, workflows |
| **.agent/workflows/** | Step-by-step procedures |

---

## Before Any Deployment

```powershell
# 1. Test locally first (ALWAYS)
./scripts/dev.ps1

# 2. For auth changes, verify
# Read: .agent/workflows/auth-verification.md

# 3. Run preflight
./scripts/preflight.ps1

# 4. Then push
git add -A
git commit -m "..."
git push origin main
```

---

## Debugging Process

```
1. Read error message carefully
2. Add debug logging (docs/ops/TROUBLESHOOTING_METHODOLOGY.md)
3. Check pattern guides:
   - Auth issues → AUTH_TROUBLESHOOTING.md
   - Schema issues → LEARNINGS_LOG.md
4. Fix and verify locally
5. Document if new pattern
```

---

## Key Principles

1. **Test locally before deploying** (scripts/dev.ps1)
2. **Debug with instrumentation, not intuition**
3. **Document patterns as you learn them**
4. **Every bug becomes a checklist item**

---

## Created This Session

- `docs/ops/TROUBLESHOOTING_METHODOLOGY.md` ← **Read this for debugging**
- `docs/ops/AUTH_TROUBLESHOOTING.md` ← JWT/auth issues
- `.agent/workflows/auth-verification.md` ← Pre-deployment checklist
- `scripts/dev.ps1` ← Local development
- `backend/test_jwt.py` ← JWT testing tool
