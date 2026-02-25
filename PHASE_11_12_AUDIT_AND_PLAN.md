# Phase 11 & 12 Audit and Implementation Plan

## Executive Summary

This document provides a comprehensive audit of the existing Deep Research system (Phases 1-10) and a detailed implementation plan for Phases 11 (Human Adjudication) and 12 (Runtime Publication + Deployment Readiness).

**Scope Lock**: No existing Phase 11/12 definitions were found in the codebase. Using default scope as specified in requirements.

---

## Part A: Codebase Audit

### A.1 State Machine Audit
**File**: `backend/modules/research_orchestrator.py` (lines 57-209)

**Current State Hierarchy**:
```
Phases 1-7: PLANNING → QUEUED → CRAWLING → AWAITING_CONFIRMATION → READY_FOR_INGESTION → INGESTING → INGESTION_COMPLETED → GENERATING_BIO → BIO_GENERATED → FINALIZING → COMPLETED

Phase 8: CLAIMS_ENRICHMENT → CLAIMS_COMPLETED
Phase 9: WEB_VERIFICATION → WEB_VERIFIED
Phase 10: CLAIMS_FINALIZATION → CLAIMS_FINALIZED (current terminal)
```

**VALID_TRANSITIONS Map**: Lines 125-209
- Pattern: Each state maps to a Set of valid next states
- Self-transitions allowed for idempotency
- Terminal states have empty sets or self-only

**Extension Points for Phase 11/12**:
- Line 204: CLAIMS_FINALIZED currently terminal (self-only)
- Need to add: CLAIMS_ADJUDICATION → CLAIMS_ADJUDICATED (Phase 11)
- Need to add: RUNTIME_PUBLICATION → RUNTIME_PUBLISHED (Phase 12)

### A.2 Database Schema Audit

**Phase 8 Tables** (`migration_phase_8_research_claims.sql`):
- `research_claims` - Core claim data with verification_status
- `research_claim_enrichment` - Progress tracking

**Phase 9 Tables** (`migration_phase_9_web_verification.sql`):
- `research_claim_web_verifications` - Web verification results
- `research_claim_web_evidence` - Supporting/conflicting evidence
- `research_web_verification_runs` - Progress tracking

**Phase 10 Tables** (`migration_phase_10_claim_finalization.sql`):
- `research_claim_finalizations` - Final decisions (lines 16-54)
- `research_claim_consistency_issues` - Cross-claim issues (lines 77-118)
- `research_claim_finalization_runs` - Progress tracking (lines 140-161)

**Migration Pattern Observed**:
- IF NOT EXISTS safety throughout
- JSONB for flexible arrays (claim_ids, reason_codes)
- Triggers for updated_at (lines 176-201)
- Unique constraints on claim_id for one-to-one relationships
- Rollback instructions in comments (lines 225-238)

### A.3 Configuration Audit
**File**: `backend/modules/deep_research_config.py`

**Existing Feature Flags** (lines 192-195):
```python
phase_8_claims_disabled: bool = Field(default=False, ...)
phase_9_web_verification_disabled: bool = Field(default=False, ...)
phase_10_claim_finalization_disabled: bool = Field(default=False, ...)
```

**Pattern**: 
- Environment variable naming: `DR_PHASE_X_NAME_DISABLED`
- from_env() loads from os.getenv() with "false" default (lines 210-214)
- is_enabled() checks master + global_disable (lines 216-218)

**Required Additions**:
- `phase_11_human_adjudication_disabled`
- `phase_12_runtime_publication_disabled`
- `phase_12_suppress_unresolved_by_default` (optional policy flag)

### A.4 Service Layer Audit

**Phase 10 Service Pattern** (`research_claim_finalization_service.py`):
- Class-based with supabase_client injection (line 95)
- Async methods with idempotency checks
- to_dict() methods on dataclasses for serialization
- Error handling with logger.error() + continue pattern

**Key Methods to Mirror**:
- `finalize_research_run()` - Orchestration entry point
- `_persist_finalization()` - Database upsert pattern
- `list_finalized_claims()` - Query with filters

### A.5 Router Pattern Audit
**File**: `backend/routers/research_claims.py`

**Current Endpoint Count**:
- Phase 8: 4 endpoints (continue-claims, claims-status, claims, resolve)
- Phase 9: 5 endpoints (continue-web-verification, web-verification-status, claims-with-web-verification, web-evidence, resolve-web)
- Phase 10: 6 endpoints (continue-claim-finalization, finalization-status, finalized-claims, consistency-issues, resolve-consistency-issue, finalize-override)

**Pattern**:
- Feature flag check functions (_check_phase_X_enabled)
- Pydantic BaseModel request/response classes
- HTTPException with structured detail dicts
- get_current_user dependency for auth
- verify_twin_ownership for authorization

### A.6 Testing Pattern Audit
**Files**: `tests/test_research_claim*.py`

**Pattern**:
- pytest with asyncio marker
- Mock fixtures from unittest.mock
- Regression test classes (TestPhase8Regression, TestPhase9Regression)
- API contract tests for enum values
- Feature flag tests with @patch("os.getenv")
- Idempotency tests

### A.7 Deployment Configuration Audit

**Render** (`render.yaml`):
- Web service + worker service
- Environment variables from sync: false (secrets)
- Health check at /health
- AutoDeploy: true

**CI/CD** (`.github/workflows/`):
- lint.yml, checkpoint.yml, code-review.yml
- persona-regression.yml for testing
- No specific deep research test workflow yet

**Environment** (`.env`):
- Feature flags not currently present
- Need to add to render.yaml for deployment

### A.8 Chat/Runtime Integration Points

**Current Status**: 
- No direct chat router integration found for claims
- Chat uses retrieval.py, sources.py
- Claims system is parallel enrichment track

**Integration Strategy for Phase 12**:
- Create separate runtime publication table
- Do NOT modify chat router in this phase
- Provide API for future chat consumption

---

## Part B: Phase 11 Implementation Plan

### B.1 Phase 11 Goal
Add Human Adjudication + Canonical Claim Review Workflow for owner/admin review of finalized claims.

### B.2 Database Schema (Additive)

**New Table: research_claim_adjudications**
```sql
CREATE TABLE IF NOT EXISTS research_claim_adjudications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Action details
    action VARCHAR(50) NOT NULL,  -- approve, reject, mark_needs_review, mark_unresolved, lock, unlock, override
    previous_status VARCHAR(50),
    new_status VARCHAR(50),
    
    -- Actor and reason
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_type VARCHAR(20) DEFAULT 'user',  -- 'user', 'system', 'admin'
    reason_code VARCHAR(50),
    notes TEXT,
    
    -- Idempotency
    idempotency_key VARCHAR(64),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_action CHECK (
        action IN ('approve', 'reject', 'mark_needs_review', 'mark_unresolved', 
                   'lock', 'unlock', 'override_status', 'override_canonical')
    ),
    CONSTRAINT valid_actor_type CHECK (actor_type IN ('user', 'system', 'admin'))
);

CREATE INDEX IF NOT EXISTS idx_claim_adjudications_claim ON research_claim_adjudications(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_adjudications_run ON research_claim_adjudications(research_run_id);
CREATE INDEX IF NOT EXISTS idx_claim_adjudications_idempotency ON research_claim_adjudications(idempotency_key);
```

**New Table: research_claim_canonical** (Current Truth Store)
```sql
CREATE TABLE IF NOT EXISTS research_claim_canonical (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Canonical state (the current reviewed truth)
    canonical_status VARCHAR(50) NOT NULL DEFAULT 'unresolved',
    canonical_text TEXT,  -- Optional normalized text
    
    -- Provenance
    source_of_truth VARCHAR(50) NOT NULL DEFAULT 'system_rule',
    -- 'system_rule' | 'human_review' | 'override' | 'consensus'
    
    -- Locking
    locked BOOLEAN DEFAULT FALSE,
    locked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    locked_at TIMESTAMPTZ,
    lock_reason TEXT,
    
    -- Confidence in this canonical version
    adjudication_confidence FLOAT DEFAULT 0.0,
    
    -- Versioning (simple)
    version INTEGER DEFAULT 1,
    superseded_by UUID REFERENCES research_claim_canonical(id),
    effective_at TIMESTAMPTZ DEFAULT NOW(),
    superseded_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_canonical_status CHECK (
        canonical_status IN ('accepted', 'rejected', 'needs_review', 'unresolved', 'superseded')
    ),
    CONSTRAINT valid_source_of_truth CHECK (
        source_of_truth IN ('system_rule', 'human_review', 'override', 'consensus')
    ),
    CONSTRAINT valid_adjudication_confidence CHECK (
        adjudication_confidence >= 0.0 AND adjudication_confidence <= 1.0
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_claim_canonical_claim_unique 
ON research_claim_canonical(claim_id) WHERE superseded_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_claim_canonical_run ON research_claim_canonical(research_run_id);
CREATE INDEX IF NOT EXISTS idx_claim_canonical_status ON research_claim_canonical(canonical_status);
CREATE INDEX IF NOT EXISTS idx_claim_canonical_locked ON research_claim_canonical(locked);
```

**Extend: research_claim_consistency_issues** (Add action history)
```sql
-- Add to existing table or create separate audit table
CREATE TABLE IF NOT EXISTS research_claim_issue_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id UUID NOT NULL REFERENCES research_claim_consistency_issues(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    action VARCHAR(50) NOT NULL,  -- confirm_conflict, dismiss, merge_duplicate, split_context, defer
    previous_status VARCHAR(20),
    new_status VARCHAR(20),
    
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason_code VARCHAR(50),
    notes TEXT,
    
    idempotency_key VARCHAR(64),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_issue_action CHECK (
        action IN ('confirm_conflict', 'dismiss', 'merge_duplicate', 'split_context', 'defer')
    )
);

CREATE INDEX IF NOT EXISTS idx_issue_actions_issue ON research_claim_issue_actions(issue_id);
```

### B.3 Service Layer

**New File: research_claim_adjudication_service.py**

Key classes:
- `AdjudicationService` - Main orchestrator
- `CanonicalClaimManager` - Manages canonical state with versioning
- `ReviewQueueBuilder` - Builds review queue views

Key methods:
- `adjudicate_claim()` - Apply human decision
- `lock_claim()` / `unlock_claim()` - Lock management
- `get_review_queue()` - Get claims needing review
- `get_canonical_claim()` - Get current truth
- `apply_consistency_issue_action()` - Issue resolution

### B.4 API Endpoints

**6 New Endpoints**:
1. `GET /review-queue/claims` - Get claims needing review
2. `GET /review-queue/summary` - Queue statistics
3. `POST /claims/{claim_id}/adjudicate` - Apply adjudication
4. `POST /claims/{claim_id}/lock` - Lock claim
5. `POST /claims/{claim_id}/unlock` - Unlock claim
6. `GET /claims/{claim_id}/adjudication-history` - View audit trail
7. `POST /consistency-issues/{issue_id}/action` - Issue action
8. `GET /consistency-issues/{issue_id}/history` - Issue audit trail
9. `GET /canonical-claims` - List canonical claims

### B.5 State Machine Extension

```python
# Phase 11: Human Adjudication
ADJUDICATION = "adjudication"
ADJUDICATED = "adjudicated"

# Add to VALID_TRANSITIONS
ResearchRunStatus.CLAIMS_FINALIZED: {
    ResearchRunStatus.ADJUDICATION,  # Optional Phase 11
    ResearchRunStatus.CLAIMS_FINALIZED,
},
ResearchRunStatus.ADJUDICATION: {
    ResearchRunStatus.ADJUDICATED,
    ResearchRunStatus.FAILED,
    ResearchRunStatus.ADJUDICATION,
},
ResearchRunStatus.ADJUDICATED: {
    ResearchRunStatus.RUNTIME_PUBLICATION,  # Optional Phase 12
    ResearchRunStatus.ADJUDICATED,
},
```

---

## Part C: Phase 12 Implementation Plan

### C.1 Phase 12 Goal
Runtime Publication + Deployment Readiness with operational integration.

### C.2 Database Schema (Additive)

**New Table: research_claim_runtime_publication**
```sql
CREATE TABLE IF NOT EXISTS research_claim_runtime_publication (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Publication state
    publishable BOOLEAN DEFAULT FALSE,
    published BOOLEAN DEFAULT FALSE,
    suppressed BOOLEAN DEFAULT FALSE,
    suppression_reason VARCHAR(50),
    
    -- Runtime fields (denormalized for query performance)
    runtime_claim_text TEXT NOT NULL,
    runtime_status VARCHAR(50) NOT NULL,  -- accepted, rejected, needs_review
    runtime_confidence FLOAT DEFAULT 0.0,
    runtime_issue_flags JSONB DEFAULT '[]'::jsonb,  -- ['has_open_issues', 'high_severity_conflict', etc.]
    
    -- Provenance (for debugging)
    source_canonical_id UUID REFERENCES research_claim_canonical(id),
    source_finalization_id UUID REFERENCES research_claim_finalizations(id),
    
    -- Publication metadata
    published_at TIMESTAMPTZ,
    published_version INTEGER DEFAULT 1,
    
    -- For incremental updates
    content_hash VARCHAR(64),  -- Detect changes
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_runtime_status CHECK (
        runtime_status IN ('accepted', 'rejected', 'needs_review', 'unpublished')
    ),
    CONSTRAINT valid_suppression_reason CHECK (
        suppression_reason IN (NULL, 'unresolved_status', 'open_consistency_issue', 'low_confidence', 'manual_hold')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_runtime_publication_claim_unique 
ON research_claim_runtime_publication(claim_id);

CREATE INDEX IF NOT EXISTS idx_runtime_publication_run 
ON research_claim_runtime_publication(research_run_id);
CREATE INDEX IF NOT EXISTS idx_runtime_publication_twin 
ON research_claim_runtime_publication(twin_id);
CREATE INDEX IF NOT EXISTS idx_runtime_publication_published 
ON research_claim_runtime_publication(published) WHERE published = TRUE;
CREATE INDEX IF NOT EXISTS idx_runtime_publication_publishable 
ON research_claim_publication(publishable) WHERE publishable = TRUE;
```

**New Table: research_claim_publication_runs**
```sql
CREATE TABLE IF NOT EXISTS research_claim_publication_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    status VARCHAR(50) DEFAULT 'pending',
    total_claims INTEGER DEFAULT 0,
    published_count INTEGER DEFAULT 0,
    suppressed_count INTEGER DEFAULT 0,
    
    backfill_mode BOOLEAN DEFAULT FALSE,
    backfill_batch INTEGER,
    
    error_message TEXT,
    
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_publication_run_status CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'partial')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_runs_research_unique 
ON research_claim_publication_runs(research_run_id);
```

### C.3 Publication Rules (Deterministic)

```python
PUBLICATION_RULES = {
    "accept_canonical_accepted": {
        "condition": "canonical_status == 'accepted'",
        "publishable": True,
        "priority": 1,
    },
    "reject_canonical_rejected": {
        "condition": "canonical_status == 'rejected'",
        "publishable": False,  # Internal only
        "suppression_reason": "rejected_claim",
        "priority": 2,
    },
    "suppress_unresolved": {
        "condition": "canonical_status == 'unresolved' AND suppress_unresolved_default",
        "publishable": False,
        "suppression_reason": "unresolved_status",
        "priority": 3,
    },
    "suppress_open_high_severity_issues": {
        "condition": "has_open_issues AND max_severity == 'high'",
        "publishable": False,
        "suppression_reason": "open_consistency_issue",
        "priority": 4,
    },
    "suppress_low_confidence": {
        "condition": "adjudication_confidence < 0.3",
        "publishable": False,
        "suppression_reason": "low_confidence",
        "priority": 5,
    },
}
```

### C.4 Service Layer

**New File: research_claim_runtime_service.py**

Key classes:
- `RuntimePublicationService` - Main publication orchestrator
- `PublicationRuleEngine` - Applies publication rules
- `BackfillService` - Handles historical backfill

Key methods:
- `publish_runtime_claims()` - Main publication entry point
- `get_runtime_claims()` - Query published claims
- `backfill_publication()` - Backfill historical runs
- `export_runtime_claims()` - Export functionality

### C.5 API Endpoints

**5 New Endpoints**:
1. `POST /publish-runtime-claims` - Trigger publication (idempotent)
2. `GET /runtime-claims` - List runtime claims
3. `GET /runtime-claims/status` - Publication status
4. `POST /runtime-claims/backfill` - Trigger backfill (admin)
5. `GET /runtime-claims/export` - Export claims (JSON/CSV)

### C.6 State Machine Extension

```python
# Phase 12: Runtime Publication
RUNTIME_PUBLICATION = "runtime_publication"
RUNTIME_PUBLISHED = "runtime_published"

# Valid transitions
ResearchRunStatus.ADJUDICATED: {
    ResearchRunStatus.RUNTIME_PUBLICATION,  # Phase 12
    ResearchRunStatus.ADJUDICATED,
},
# OR from CLAIMS_FINALIZED if Phase 11 disabled
ResearchRunStatus.CLAIMS_FINALIZED: {
    ResearchRunStatus.ADJUDICATION,
    ResearchRunStatus.RUNTIME_PUBLICATION,  # Direct to Phase 12
    ResearchRunStatus.CLAIMS_FINALIZED,
},
ResearchRunStatus.RUNTIME_PUBLICATION: {
    ResearchRunStatus.RUNTIME_PUBLISHED,
    ResearchRunStatus.FAILED,
    ResearchRunStatus.RUNTIME_PUBLICATION,
},
ResearchRunStatus.RUNTIME_PUBLISHED: {
    ResearchRunStatus.RUNTIME_PUBLISHED,  # Terminal
},
```

---

## Part D: Deployment Readiness Plan

### D.1 Migration Rollout Safety

**Order of Execution**:
1. `migration_phase_11_human_adjudication.sql` - Phase 11 tables
2. `migration_phase_12_runtime_publication.sql` - Phase 12 tables
3. Both use IF NOT EXISTS - safe to rerun

**Rollback**:
- Each migration has rollback section in comments
- Phase 8/9/10 data remains untouched
- Can disable via feature flags without rollback

### D.2 Feature Flag Rollout Sequence

**Recommended Rollout**:
1. Deploy code with flags enabled (disabled by default)
2. Enable Phase 11 for test twins
3. Enable Phase 12 for test twins
4. Gradual rollout: 10% → 50% → 100%
5. Monitor metrics at each stage

### D.3 Observability Plan

**Metrics to Add**:
- `claims_adjudication_actions_total` (counter, labels: action, actor_type)
- `canonical_claims_locked_total` (gauge)
- `consistency_issue_actions_total` (counter, labels: action)
- `runtime_publication_runs_total` (counter, labels: status)
- `runtime_publication_failures_total` (counter)
- `runtime_claims_published_total` (counter)
- `runtime_claims_suppressed_total` (counter, labels: reason)

**Structured Logging**:
- Use existing logger pattern
- Add correlation_id for tracing
- Log all adjudication actions

### D.4 Backfill Strategy

**CLI Entrypoint**: `scripts/backfill_phase_12.py`

Features:
- Dry-run mode (--dry-run)
- Batch sizing (--batch-size 100)
- Resume capability (track last processed run)
- Target specific research runs (--run-id)
- Progress logging

---

## Part E: Files to Create/Modify

### New Files (10)
1. `backend/database/migrations/migration_phase_11_human_adjudication.sql`
2. `backend/database/migrations/migration_phase_12_runtime_publication.sql`
3. `backend/modules/research_claim_adjudication_service.py`
4. `backend/modules/research_claim_runtime_service.py`
5. `backend/tests/test_research_claim_adjudication.py`
6. `backend/tests/test_research_claim_runtime.py`
7. `scripts/backfill_phase_12.py`
8. `scripts/smoke_test_phases_11_12.py`
9. `PHASE_11_12_DEPLOYMENT_RUNBOOK.md`
10. `.env.example` (update with new flags)

### Modified Files (5)
1. `backend/modules/deep_research_config.py` - Add Phase 11/12 flags
2. `backend/modules/research_orchestrator.py` - Extend state machine
3. `backend/routers/research_claims.py` - Add new endpoints
4. `render.yaml` - Add new env vars
5. `.github/workflows/persona-regression.yml` - Extend test coverage

---

## Part F: Testing Strategy

### Unit Tests
- Adjudication rule engine
- Canonical versioning logic
- Publication rule engine
- Lock/unlock behavior

### Integration Tests
- Full adjudication flow
- Full publication flow
- Backfill dry-run and execution
- Idempotency verification

### Regression Tests
- Phase 8, 9, 10 endpoints unchanged
- State machine backward compatibility
- Feature flag behavior

### Smoke Tests
- App boots with new code
- Migrations apply cleanly
- Endpoints respond
- Sample flow: finalization → adjudication → publication

---

## Part G: Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking Phase 8-10 | Low | High | Comprehensive regression tests |
| Migration failure | Low | Medium | IF NOT EXISTS, rollback docs |
| Performance issues | Medium | Medium | Indexes, batch processing |
| Feature flag confusion | Medium | Low | Clear naming, documentation |
| Data inconsistency | Low | High | Idempotency, audit trails |

---

## Part H: STOP Confirmation

**Phase 11/12 Boundary**:
- ✅ Human adjudication workflow
- ✅ Canonical claim store
- ✅ Runtime publication
- ✅ Deployment readiness
- ❌ Chat UI integration (future)
- ❌ Real-time sync (future)
- ❌ Advanced analytics dashboard (future)
- ❌ Phase 13+ features

**No Phase 13 work will be done.**

---

## Appendix: Naming Conventions

Following existing codebase patterns:
- Tables: `research_claim_*`, `research_*_runs`
- Services: `ResearchClaim*Service`
- Feature flags: `DR_PHASE_X_*_DISABLED`
- States: `SCREAMING_SNAKE_CASE`
- Endpoints: `kebab-case`

---

*Document Version: 1.0*
*Created: 2026-02-24*
*Audit Complete: Ready for Implementation*
