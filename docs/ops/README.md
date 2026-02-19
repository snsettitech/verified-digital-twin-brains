# Operations Quick Reference

## Core Documents

| Document | When To Use |
|----------|-------------|
| **PRODUCTION_DEPLOYMENT_RUNBOOK.md** | Deploying to production |
| **TROUBLESHOOTING_METHODOLOGY.md** | Debugging any issue |
| **AUTH_TROUBLESHOOTING.md** | 401/403 errors, JWT issues |
| **WORKER_SETUP_GUIDE.md** | Background job processing |
| **QUALITY_GATE.md** | Pre-merge quality checks |
| **RUNBOOKS.md** | Operational procedures |

## Before Any Deployment

```bash
# 1. Run preflight checks
./scripts/preflight.ps1    # Windows
./scripts/preflight.sh     # Linux/Mac

# 2. For auth changes, verify
# Read: .agent/workflows/auth-verification.md

# 3. Push
git push origin main
```

## Debugging Process

1. Read error message carefully
2. Add debug logging (see TROUBLESHOOTING_METHODOLOGY.md)
3. Check pattern guides:
   - Auth issues -> AUTH_TROUBLESHOOTING.md
   - Known blockers -> ../KNOWN_FAILURES.md
   - Feature limits -> ../KNOWN_LIMITATIONS.md
4. Fix and verify locally
5. Run preflight before pushing
