# Phase 6 Deployment Runbook

## Overview

This document provides deployment guidance for the Firecrawl-only Deep Research system (Phases 3.0-6.0).

## Prerequisites

- Firecrawl API key configured
- Database migrations applied (Phases 3.0-3.4)
- Environment variables set

## Required Environment Variables

### Firecrawl Configuration
```bash
# Required
FIRECRAWL_API_KEY=your_api_key_here

# Optional (with defaults)
FIRECRAWL_MAX_PAGES=50
FIRECRAWL_MAX_DEPTH=2
FIRECRAWL_REQUEST_TIMEOUT=30
```

### Feature Flags (Phase Gating)
```bash
# Master switch
DEEP_RESEARCH_ENABLED=true

# Global kill switch (emergency disable)
# DEEP_RESEARCH_GLOBAL_DISABLE=true

# Phase-specific flags (disable specific phases)
# DR_PHASE_3_5_DISABLED=true      # Disable ingestion continuation
# DR_PHASE_4_BIO_DISABLED=true    # Disable bio generation
# DR_PHASE_5_FINALIZE_DISABLED=true # Disable finalization
```

### Readiness Threshold
```bash
# Minimum mind score for twin readiness (default: 30)
DR_MIN_READY_MIND_SCORE=30
```

## Migration Order

1. **Pre-deployment**
   ```bash
   # Run database migrations
   psql -f backend/database/migrations/migration_phase_3_0_firecrawl_foundation.sql
   psql -f backend/database/migrations/migration_phase_3_3_source_confirmation.sql
   psql -f backend/database/migrations/migration_phase_3_4_research_orchestrator.sql
   ```

2. **Deployment**
   - Deploy backend code
   - Verify feature flags
   - Run smoke tests

3. **Post-deployment**
   - Monitor logs for errors
   - Verify endpoint health
   - Check feature flag behavior

## Enablement Sequence by Feature Flags

### Gradual Rollout

1. **Phase 3.0-3.4 (Foundation)**
   ```bash
   DEEP_RESEARCH_ENABLED=true
   # All other phase flags unset (default enabled)
   ```

2. **Phase 3.5 (Ingestion)**
   ```bash
   DEEP_RESEARCH_ENABLED=true
   # DR_PHASE_3_5_DISABLED=false (or unset)
   ```

3. **Phase 4 (Bio Generation)**
   ```bash
   DEEP_RESEARCH_ENABLED=true
   DR_PHASE_3_5_DISABLED=false
   DR_PHASE_4_BIO_DISABLED=false
   ```

4. **Phase 5 (Finalization)**
   ```bash
   DEEP_RESEARCH_ENABLED=true
   DR_PHASE_3_5_DISABLED=false
   DR_PHASE_4_BIO_DISABLED=false
   DR_PHASE_5_FINALIZE_DISABLED=false
   ```

## Rollback Steps

### Emergency Rollback

1. **Disable all research endpoints**
   ```bash
   DEEP_RESEARCH_GLOBAL_DISABLE=true
   ```

2. **Disable specific phase**
   ```bash
   # Example: Disable Phase 5 only
   DR_PHASE_5_FINALIZE_DISABLED=true
   ```

3. **Verify rollback**
   ```bash
   # Check endpoints return 503
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.example.com/twins/$TWIN_ID/research-summary
   ```

### Schema Safety

All schema changes are **additive only**:
- New columns use `IF NOT EXISTS`
- No destructive migrations
- Old code can run against new schema
- Rollback does not require schema changes

## Smoke Test Commands

### Staging Verification

```bash
#!/bin/bash
set -e

BASE_URL="https://api.staging.example.com"
TOKEN="your_test_token"
TWIN_ID="test-twin-123"

echo "1. Health check"
curl -s "$BASE_URL/health" | jq -r '.status'

echo "2. Create research run"
RUN_RESPONSE=$(curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"claimed_identity":{"full_name":"Test"},"seed_urls":["https://example.com"]}' \
  "$BASE_URL/twins/$TWIN_ID/research")
RUN_ID=$(echo $RUN_RESPONSE | jq -r '.research_run_id')
echo "Created run: $RUN_ID"

echo "3. Get research status"
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/twins/$TWIN_ID/research/$RUN_ID" | jq -r '.status'

echo "4. Get pending confirmations"
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/twins/$TWIN_ID/research/$RUN_ID/pending-confirmations" | jq '.items | length'

echo "5. Get research summary"
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/twins/$TWIN_ID/research-summary" | jq -r '.status // "no-run"'

echo "Smoke tests complete!"
```

### Feature Flag Testing

```bash
# Test Phase 5 disabled
DR_PHASE_5_FINALIZE_DISABLED=true

# Should return 503
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/twins/$TWIN_ID/research/$RUN_ID/continue-finalize"
# Expected: {"error": "Phase 5 finalization is disabled", ...}
```

## API Contract Reference

### Canonical Field Names (Phase 6)

| Endpoint | Response Field | Type | Description |
|----------|---------------|------|-------------|
| All status endpoints | `next_actions` | `List[str]` | Canonical plural field |
| All status endpoints | `next_action` | `str` | Backward compat alias |

### Key Response Contracts

```typescript
// ResearchSummaryResponse
interface ResearchSummaryResponse {
  twin_id: string;
  research_run_id?: string;
  status?: string;
  sources: {
    confirmed: Source[];
    auto_confirmed: Source[];
    pending: Source[];
    manual_review: Source[];
    rejected: Source[];
  };
  bio_generation?: BioGenerationSummary;
  mind_score?: MindScoreSummary;
  readiness?: ReadinessSummary;
  next_actions: string[];  // Canonical plural field
  checkpoint_updated_at?: string;
}

// ResearchRunStatusResponse
interface ResearchRunStatusResponse {
  research_run_id: string;
  twin_id: string;
  status: string;
  crawl_id?: string;
  checkpoint_data: object;
  confirmation_summary?: object;
  next_actions: string[];  // Canonical plural field
  warnings: string[];
  created_at: string;
  updated_at: string;
}
```

## Monitoring Checklist

- [ ] No errors in `/var/log/backend/research-orchestrator.log`
- [ ] Feature flag endpoints return expected responses
- [ ] Research run creation < 2s latency
- [ ] Status polling < 500ms latency
- [ ] Confirmation endpoints < 1s latency
- [ ] No 500 errors on continue-* endpoints

## Troubleshooting

### Issue: Phase endpoint returns 503

**Cause**: Feature flag disabled

**Fix**:
```bash
# Check flag
printenv | grep DR_PHASE

# Enable if needed
unset DR_PHASE_X_DISABLED
```

### Issue: Research run stuck in "planning"

**Cause**: Async worker not processing

**Fix**:
```bash
# Check worker logs
tail -f /var/log/backend/worker.log

# Restart worker
systemctl restart backend-worker
```

### Issue: Confirmations not created

**Cause**: Crawl not completed or error in confirmation creation

**Fix**:
```bash
# Check crawl status
curl -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/twins/$TWIN_ID/crawls/$CRAWL_ID"
```

## Contact

For deployment issues, contact:
- Backend Team: backend-team@example.com
- On-Call: oncall@example.com

---

**Last Updated**: Phase 6 Implementation  
**Version**: 6.0.0
