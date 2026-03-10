# Phase 11 & 12 Deployment Runbook

## Executive Summary

This runbook provides step-by-step instructions for deploying Phases 11 (Human Adjudication) and 12 (Runtime Publication) of the Deep Research system.

**Status**: Ready for deployment  
**Risk Level**: Low (additive changes, feature-flagged)  
**Estimated Deployment Time**: 30-45 minutes  

---

## Pre-Deployment Checklist

### 1. Code Review Complete
- [ ] Phase 11 database migrations reviewed
- [ ] Phase 12 database migrations reviewed
- [ ] Service layer code reviewed
- [ ] API endpoints reviewed
- [ ] Feature flags configured

### 2. Environment Preparation
- [ ] Database backup completed
- [ ] Render.yaml updated with new env vars
- [ ] .env.example updated
- [ ] CI/CD pipeline validated

### 3. Testing Complete
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Migration dry-run successful
- [ ] Smoke tests pass

---

## Deployment Steps

### Step 1: Database Migrations (5 minutes)

Run the migrations in order:

```bash
# Phase 11: Human Adjudication Tables
psql $DATABASE_URL < backend/database/migrations/migration_phase_11_human_adjudication.sql

# Phase 12: Runtime Publication Tables
psql $DATABASE_URL < backend/database/migrations/migration_phase_12_runtime_publication.sql
```

**Verification**:
```sql
-- Check Phase 11 tables
SELECT COUNT(*) FROM research_claim_adjudications;
SELECT COUNT(*) FROM research_claim_canonical;

-- Check Phase 12 tables
SELECT COUNT(*) FROM research_claim_runtime_publication;
SELECT COUNT(*) FROM research_claim_publication_runs;
```

### Step 2: Feature Flags (2 minutes)

Set environment variables in Render dashboard:

```bash
# Phase 11 - Disabled initially
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=true

# Phase 12 - Disabled initially
DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=true
DR_PHASE_12_SUPPRESS_UNRESOLVED=true
DR_PHASE_12_AUTO_PUBLISH=false
```

### Step 3: Deploy Code (10 minutes)

```bash
# Push to main branch
git add .
git commit -m "Deploy Phases 11-12: Human Adjudication + Runtime Publication"
git push origin main
```

**Monitor deployment**:
```bash
# Check Render deployment logs
# Wait for health check to pass
```

### Step 4: Smoke Tests (10 minutes)

```bash
# Run smoke test script
python scripts/smoke_test_phases_11_12.py
```

**Manual verification**:
1. Check `/health` endpoint returns 200
2. Check Phase 8/9/10 endpoints still work
3. Check Phase 11 endpoints return 503 (disabled)
4. Check Phase 12 endpoints return 503 (disabled)

---

## Gradual Rollout

### Phase 11 Rollout (Week 1-2)

1. **Enable for test twin**:
```bash
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=false
```

2. **Test adjudication workflow**:
- GET `/review-queue` - View claims needing review
- POST `/claims/{id}/adjudicate` - Approve/reject claims
- POST `/claims/{id}/lock` - Lock claims
- GET `/claims/{id}/adjudication-history` - View audit trail

3. **Monitor metrics**:
- `claims_adjudication_actions_total`
- `canonical_claims_locked_total`

4. **Gradual expansion**:
- Week 1: 10% of twins
- Week 2: 50% of twins
- Week 3: 100% of twins

### Phase 12 Rollout (Week 3-4)

1. **Enable for test twin**:
```bash
DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=false
```

2. **Test publication workflow**:
- POST `/publish-runtime-claims` - Publish claims
- GET `/runtime-claims` - View published claims
- GET `/runtime-claims/status` - Check status

3. **Optional: Run backfill**:
```bash
python scripts/backfill_phase_12.py --twin-id <test-twin> --dry-run
python scripts/backfill_phase_12.py --twin-id <test-twin>
```

4. **Gradual expansion**:
- Week 3: 10% of twins
- Week 4: 50% → 100% of twins

---

## Rollback Procedures

### Emergency Rollback (5 minutes)

If critical issues are detected:

```bash
# Disable all new features
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=true
DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=true

# Redeploy (or set in Render dashboard)
```

**No data migration needed** - Phase 8/9/10 data remains intact.

### Database Rollback (if needed)

```sql
-- Rollback Phase 12
DROP TABLE IF EXISTS research_claim_publication_audit;
DROP TABLE IF EXISTS research_claim_publication_config;
DROP TABLE IF EXISTS research_claim_publication_runs;
DROP TABLE IF EXISTS research_claim_runtime_publication;
DROP FUNCTION IF EXISTS update_phase12_updated_at();

-- Rollback Phase 11
DROP TABLE IF EXISTS research_claim_adjudication_runs;
DROP TABLE IF EXISTS research_claim_issue_actions;
DROP TABLE IF EXISTS research_claim_canonical;
DROP TABLE IF EXISTS research_claim_adjudications;
DROP FUNCTION IF EXISTS update_phase11_updated_at();
```

---

## Observability

### Metrics to Monitor

| Metric | Alert Threshold | Description |
|--------|-----------------|-------------|
| `claims_adjudication_actions_total` | N/A | Counter of adjudication actions |
| `runtime_publication_runs_total` | > 0 failed/hour | Publication run status |
| `runtime_claims_published_total` | N/A | Successfully published claims |
| `runtime_claims_suppressed_total` | > 50% | Claims suppressed (investigate) |
| API error rate | > 1% | Phase 11/12 endpoint errors |

### Logs to Watch

```bash
# Filter for Phase 11/12 logs
grep "phase_11\|phase_12\|adjudication\|runtime" /var/log/app.log

# Check for errors
grep "ERROR.*adjudication\|ERROR.*runtime" /var/log/app.log
```

### Database Queries for Health Check

```sql
-- Pending adjudications (should decrease over time)
SELECT COUNT(*) FROM research_claim_canonical 
WHERE canonical_status IN ('needs_review', 'unresolved');

-- Publication status summary
SELECT 
    published,
    suppressed,
    suppression_reason,
    COUNT(*)
FROM research_claim_runtime_publication
GROUP BY published, suppressed, suppression_reason;

-- Recent adjudication actions
SELECT action, COUNT(*) 
FROM research_claim_adjudications 
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY action;
```

---

## Troubleshooting

### Issue: Migration Fails

**Symptoms**: Deployment fails at migration step  
**Cause**: Table already exists or constraint violation  
**Solution**:
```sql
-- Check existing tables
\dt research_claim_*

-- If needed, manually add missing columns/indexes
-- (Migration uses IF NOT EXISTS, should be safe to re-run)
```

### Issue: Phase 11 Endpoints Return 500

**Symptoms**: `/review-queue` returns error  
**Cause**: Missing table or column  
**Solution**:
```sql
-- Verify tables exist
SELECT * FROM research_claim_adjudications LIMIT 1;
SELECT * FROM research_claim_canonical LIMIT 1;

-- Check for missing indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'research_claim_adjudications';
```

### Issue: Claims Not Publishing (Phase 12)

**Symptoms**: All claims suppressed, none published  
**Cause**: All claims in `unresolved` status, suppression rule active  
**Solution**:
```sql
-- Check claim statuses
SELECT canonical_status, COUNT(*) 
FROM research_claim_canonical 
GROUP BY canonical_status;

-- Either adjudicate claims first (Phase 11)
-- Or temporarily disable suppression
DR_PHASE_12_SUPPRESS_UNRESOLVED=false
```

---

## Post-Deployment Verification

### 1. Health Check (2 minutes)
```bash
curl https://<your-domain>/health
# Should return {"status": "ok"}
```

### 2. Feature Flag Check (2 minutes)
```bash
# Phase 11 (should return 503 - disabled)
curl -H "Authorization: Bearer $TOKEN" \
  https://<your-domain>/twins/<twin>/research/<run>/review-queue

# Phase 12 (should return 503 - disabled)
curl -H "Authorization: Bearer $TOKEN" \
  https://<your-domain>/twins/<twin>/runtime-claims
```

### 3. Existing Functionality (5 minutes)
```bash
# Phase 8 - Should work
curl -H "Authorization: Bearer $TOKEN" \
  https://<your-domain>/twins/<twin>/research/<run>/claims

# Phase 10 - Should work
curl -H "Authorization: Bearer $TOKEN" \
  https://<your-domain>/twins/<twin>/research/<run>/finalized-claims
```

### 4. Enable and Test (after gradual rollout)
```bash
# Enable Phase 11 for test twin
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=false

# Test review queue
curl -H "Authorization: Bearer $TOKEN" \
  https://<your-domain>/twins/<twin>/research/<run>/review-queue

# Test adjudication
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "notes": "Test adjudication"}' \
  https://<your-domain>/twins/<twin>/research/<run>/claims/<claim>/adjudicate
```

---

## Success Criteria

### Deployment Success
- [ ] All migrations applied without errors
- [ ] Application starts and passes health check
- [ ] Phase 8/9/10 endpoints continue to work
- [ ] Feature flags are respected (disabled features return 503)

### Phase 11 Success
- [ ] Review queue endpoint returns claims
- [ ] Adjudication actions are recorded in audit trail
- [ ] Canonical claim versions are created
- [ ] Lock/unlock mechanism works

### Phase 12 Success
- [ ] Publication rules correctly evaluate claims
- [ ] Published claims are queryable
- [ ] Suppression reasons are accurate
- [ ] Backfill service processes historical runs

---

## Contact Information

| Role | Contact | Escalation |
|------|---------|------------|
| Primary On-Call | #engineering-alerts | - |
| Database Issues | #database-team | Page if > 1 hour |
| Security Issues | #security-team | Page immediately |

---

## Appendix

### Environment Variables Reference

```bash
# Phase 11
DR_PHASE_11_HUMAN_ADJUDICATION_DISABLED=true|false

# Phase 12
DR_PHASE_12_RUNTIME_PUBLICATION_DISABLED=true|false
DR_PHASE_12_SUPPRESS_UNRESOLVED=true|false
DR_PHASE_12_AUTO_PUBLISH=true|false
```

### API Endpoints Summary

**Phase 11 Endpoints**:
- GET `/twins/{twin}/research/{run}/review-queue`
- GET `/twins/{twin}/research/{run}/review-queue/summary`
- POST `/twins/{twin}/research/{run}/claims/{claim}/adjudicate`
- POST `/twins/{twin}/research/{run}/claims/{claim}/lock`
- POST `/twins/{twin}/research/{run}/claims/{claim}/unlock`
- GET `/twins/{twin}/research/{run}/claims/{claim}/adjudication-history`
- POST `/twins/{twin}/research/{run}/consistency-issues/{issue}/action`

**Phase 12 Endpoints**:
- POST `/twins/{twin}/research/{run}/publish-runtime-claims`
- GET `/twins/{twin}/runtime-claims`
- GET `/twins/{twin}/research/{run}/runtime-claims/status`
- POST `/admin/runtime-claims/backfill`
- POST `/twins/{twin}/runtime-claims/export`

---

*Runbook Version: 1.0*  
*Last Updated: 2026-02-24*  
*Author: Deep Research Implementation Team*
