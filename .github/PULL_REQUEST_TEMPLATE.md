## Summary

One to three sentences describing the change and why it matters.

## Agent And Area

- Agent: [ ] Codex  [ ] Antigravity  [ ] Human
- Area: [ ] Backend  [ ] Frontend  [ ] Infra/CI  [ ] Docs

## Related Issues

- Fixes: #
- Related: #

## Scope

### Included

- 

### Not Included

- 

## What Changed

- Files touched:
  - 
- Key changes:
  - 
- API or contract changes:
  - N/A

## How To Verify

### Local

1. 
2. 
3. 

Commands:

```bash
./scripts/preflight.ps1
```

### Manual Flow

- User flow:
- Edge cases:

If not applicable, write `N/A`.

## Evidence

Attach at least one of:

- test output
- logs
- screenshots or short recording for UI changes

If none, explain why.

## Risk Assessment

- Risk level: [ ] Low  [ ] Medium  [ ] High
- Why:
- Potential failure modes:
- Mitigations:
- Rollback plan: `git revert <sha>` or equivalent steps

## Checklist

### Quality

- [ ] CI checks pass
- [ ] No debug logs, temp files, or generated residue were committed
- [ ] PR is small and single-purpose, or the size is justified

### Security And Multi-Tenancy

- [ ] No secrets or `.env` files committed
- [ ] No PII logged or exposed
- [ ] DB queries are scoped by `tenant_id` or `twin_id` where applicable
- [ ] Auth is enforced where required
- [ ] Ownership/access checks are enforced where required

### Data And Migrations

- [ ] Migration included and reversible, if applicable
- [ ] Backfill/verification plan documented, if applicable

### Documentation

- [ ] README/runbook/docs updated, if applicable
