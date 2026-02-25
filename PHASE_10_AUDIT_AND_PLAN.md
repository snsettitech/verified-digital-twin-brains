# Phase 10: Claims Finalization + Cross-Claim Consistency Review - Audit & Plan

## 1. Phase 10 Compatibility Audit

### Phase 8 Infrastructure (Existing)

**Database Schema:**
- `research_claims` table: Core claims with Phase 8 local verification
  - `verification_status`: pending, supported, insufficient_evidence, conflicting, needs_review
  - `confidence`: 0.0-1.0
  - `evidence_quotes`: JSONB array
  - `source_id`, `source_url`, `source_title`: Source citation

- `research_claim_enrichment` table: Tracks Phase 8 enrichment progress
  - `research_run_id`, `status`, counts by status

### Phase 9 Infrastructure (Existing)

**Database Schema:**
- `research_claim_web_verifications` table: Web verification results
  - `claim_id` (unique constraint): One web verification per claim
  - `web_verification_status`: pending, supported, conflicting, insufficient_evidence, needs_review, blocked, error, skipped
  - `web_verification_confidence`: 0.0-1.0
  - `sources_searched`, `sources_found`, `supporting_evidence_count`, `conflicting_evidence_count`

- `research_claim_web_evidence` table: Individual web evidence items
  - `verification_id`, `claim_id`, `source_url`, `evidence_type` (supporting/conflicting/neutral)

- `research_web_verification_runs` table: Tracks Phase 9 progress per research run

### State Machine (Current)

```
Phase 5: COMPLETED
    ↓ (optional)
Phase 8: CLAIMS_ENRICHMENT → CLAIMS_COMPLETED
    ↓ (optional)
Phase 9: WEB_VERIFICATION → WEB_VERIFIED (terminal)
```

**Current Terminal States:**
- `FAILED` (always terminal)
- `WEB_VERIFIED` (Phase 9 terminal, but will become non-terminal for Phase 10)
- All other phases 1-7 terminals are non-terminal when Phase 8+ enabled

### API Endpoints (Current)

**Phase 8:**
- `POST /continue-claims`
- `GET /claims-status`
- `GET /claims`
- `POST /claims/{id}/resolve`

**Phase 9:**
- `POST /continue-web-verification`
- `GET /web-verification-status`
- `GET /claims-with-web-verification`
- `GET /claims/{id}/web-evidence`
- `POST /claims/{id}/resolve-web`

### Feature Flags (Current)

- `DEEP_RESEARCH_ENABLED` - Master switch
- `DEEP_RESEARCH_GLOBAL_DISABLE` - Emergency kill switch
- `DR_PHASE_8_CLAIMS_DISABLED` - Disable Phase 8
- `DR_PHASE_9_WEB_VERIFICATION_DISABLED` - Disable Phase 9

### Attachment Points for Phase 10

1. **Database**: New tables for finalization and consistency issues
2. **State Machine**: Extend from `WEB_VERIFIED` → `CLAIMS_FINALIZATION` → `CLAIMS_FINALIZED`
3. **Service**: New finalization service that reads Phase 8 + 9 data, writes Phase 10
4. **API**: New endpoints under existing prefix

**Key Design Decision:**
- Phase 10 requires `WEB_VERIFIED` state (does NOT support `CLAIMS_COMPLETED` directly)
- This keeps the logic clean: finalization always has web verification if available
- `WEB_VERIFIED` becomes non-terminal when Phase 10 is enabled

---

## 2. Phase 10 Implementation Plan

### Phase 10 Goal
Add Claims Finalization + Cross-Claim Consistency Review MVP:
1. Combine Phase 8 local + Phase 9 web verification into final claim decision
2. Detect contradictions/inconsistencies across claims
3. Expose review APIs + lightweight UI
4. Keep all prior phases backward compatible

### Architecture Principles
1. **Additive Only**: Phase 10 does NOT modify Phase 8 or 9 data
2. **Optional Step**: Runs after `WEB_VERIFIED`, which remains terminal when disabled
3. **Separate Storage**: Finalization in new tables, no mutation to Phase 8/9
4. **Deterministic Rules**: Rule-based adjudication, testable, no heavy reasoning
5. **Audit Trail**: Manual overrides tracked with user + timestamp

---

## 3. Implementation Details

### 3.1 Database Migration
**File**: `backend/database/migrations/migration_phase_10_claim_finalization.sql`

```sql
-- Final claim decisions
CREATE TABLE IF NOT EXISTS research_claim_finalizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Final decision (additive, separate from Phase 8/9)
    final_status VARCHAR(50) DEFAULT 'unresolved',
    final_confidence FLOAT DEFAULT 0.0,
    final_reason_codes JSONB DEFAULT '[]'::jsonb,
    
    -- Resolution metadata
    resolution_source VARCHAR(50) DEFAULT 'system_rule',
    finalized_by UUID REFERENCES users(id) ON DELETE SET NULL,
    finalized_at TIMESTAMPTZ,
    
    -- Inputs that determined the decision (for audit)
    local_verification_status VARCHAR(50),
    local_confidence FLOAT,
    web_verification_status VARCHAR(50),
    web_confidence FLOAT,
    
    -- Notes
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_final_status CHECK (
        final_status IN ('accepted', 'rejected', 'needs_review', 'unresolved', 'overridden')
    ),
    CONSTRAINT valid_resolution_source CHECK (
        resolution_source IN ('system_rule', 'manual_override', 'consistency_review')
    )
);

-- Unique constraint: one finalization per claim
CREATE UNIQUE INDEX IF NOT EXISTS idx_claim_finalizations_claim_unique 
ON research_claim_finalizations(claim_id);

-- Consistency issues
CREATE TABLE IF NOT EXISTS research_claim_consistency_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    issue_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    
    -- Claim IDs involved (JSONB array for flexibility)
    claim_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Issue description
    title TEXT NOT NULL,
    description TEXT,
    
    -- Detection metadata
    detection_rule VARCHAR(100),
    confidence FLOAT DEFAULT 0.0,
    
    -- Resolution
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    resolution_action VARCHAR(50), -- 'dismissed', 'claims_updated', etc.
    
    -- Deduplication hash
    issue_hash VARCHAR(64),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT valid_issue_type CHECK (
        issue_type IN ('contradiction', 'duplicate', 'confidence_mismatch', 'status_conflict')
    ),
    CONSTRAINT valid_severity CHECK (severity IN ('low', 'medium', 'high')),
    CONSTRAINT valid_status CHECK (status IN ('open', 'resolved', 'dismissed')),
    CONSTRAINT valid_resolution_action CHECK (
        resolution_action IN (NULL, 'dismissed', 'claims_updated', 'manual_override')
    )
);

-- Finalization run tracking
CREATE TABLE IF NOT EXISTS research_claim_finalization_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    status VARCHAR(50) DEFAULT 'pending',
    total_claims INTEGER DEFAULT 0,
    finalized_count INTEGER DEFAULT 0,
    issues_found INTEGER DEFAULT 0,
    
    error_message TEXT,
    
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_claim_finalizations_run ON research_claim_finalizations(research_run_id);
CREATE INDEX IF NOT EXISTS idx_claim_finalizations_status ON research_claim_finalizations(final_status);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_run ON research_claim_consistency_issues(research_run_id);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_status ON research_claim_consistency_issues(status);
CREATE INDEX IF NOT EXISTS idx_consistency_issues_hash ON research_claim_consistency_issues(issue_hash);
```

### 3.2 Backend Modules

#### Module 1: Claim Finalization Engine
**File**: `backend/modules/research_claim_finalization_engine.py`

```python
class FinalizationEngine:
    """
    Deterministic rule-based claim finalization.
    Combines Phase 8 local + Phase 9 web verification.
    """
    
    def finalize_claim(
        self,
        claim: ResearchClaim,
        local_status: VerificationStatus,
        local_confidence: float,
        web_status: Optional[WebVerificationStatus],
        web_confidence: float,
    ) -> FinalizationDecision:
        """
        Apply rules to determine final status.
        
        Rules (MVP):
        1. If local == supported AND web == supported -> accepted
        2. If local == conflicting OR web == conflicting -> rejected
        3. If local == needs_review OR web == needs_review -> needs_review
        4. If web is None (not run) AND local == supported -> accepted (with note)
        5. If local != web (conflict) -> needs_review
        6. Otherwise -> unresolved
        """

@dataclass
class FinalizationDecision:
    final_status: FinalClaimStatus
    final_confidence: float
    reason_codes: List[str]
    notes: str
```

#### Module 2: Consistency Checker
**File**: `backend/modules/research_claim_consistency_checker.py`

```python
class ConsistencyChecker:
    """
    Detects contradictions and issues across claims in a research run.
    """
    
    def check_consistency(
        self,
        claims: List[FinalizedClaim]
    ) -> List[ConsistencyIssue]:
        """
        Run heuristics to find issues:
        1. Opposite preferences (prefer X vs dislike X)
        2. Conflicting facts with same subject
        3. Duplicate claims with different statuses
        4. High confidence vs low confidence contradictions
        """
    
    def _detect_contradictions(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]
    def _detect_duplicates(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]
    def _detect_confidence_mismatches(self, claims: List[FinalizedClaim]) -> List[ConsistencyIssue]

@dataclass
class ConsistencyIssue:
    issue_type: str  # 'contradiction', 'duplicate', 'confidence_mismatch', 'status_conflict'
    severity: str    # 'low', 'medium', 'high'
    claim_ids: List[str]
    title: str
    description: str
    detection_rule: str
    confidence: float
    issue_hash: str  # For deduplication
```

#### Module 3: Finalization Service
**File**: `backend/modules/research_claim_finalization_service.py`

```python
class ResearchClaimFinalizationService:
    """
    Orchestrates finalization for research runs.
    """
    
    async def finalize_research_run(
        self,
        research_run_id: str,
        twin_id: str,
    ) -> FinalizationSummary:
        """
        1. Fetch all claims with Phase 8 + 9 data
        2. Apply finalization rules to each
        3. Persist final decisions
        4. Run consistency checker
        5. Persist issues
        6. Return summary
        """
    
    async def resolve_consistency_issue(
        self,
        issue_id: str,
        action: str,  # 'dismiss', 'update_claims', 'manual_override'
        notes: str,
        user_id: str,
    ) -> bool
    
    async def manual_override_final_status(
        self,
        claim_id: str,
        new_status: FinalClaimStatus,
        reason: str,
        user_id: str,
    ) -> bool
```

### 3.3 State Machine Extension

**Add to orchestrator:**
```python
class ResearchRunStatus(str, Enum):
    # ... existing ...
    WEB_VERIFIED = "web_verified"  # Phase 9 terminal → non-terminal
    
    # Phase 10: Claim Finalization
    CLAIMS_FINALIZATION = "claims_finalization"
    CLAIMS_FINALIZED = "claims_finalized"  # Phase 10 terminal

VALID_TRANSITIONS[ResearchRunStatus.WEB_VERIFIED] = {
    ResearchRunStatus.CLAIMS_FINALIZATION,
    ResearchRunStatus.WEB_VERIFIED,  # Self for idempotency
}

VALID_TRANSITIONS[ResearchRunStatus.CLAIMS_FINALIZATION] = {
    ResearchRunStatus.CLAIMS_FINALIZED,
    ResearchRunStatus.FAILED,
    ResearchRunStatus.CLAIMS_FINALIZATION,  # Self for idempotency
}
```

### 3.4 API Endpoints

**File**: `backend/routers/research_claims.py` (extend)

```python
# Continue to finalization
POST /twins/{twin_id}/research/{research_run_id}/continue-claim-finalization
Response: FinalizationResponse

# Get finalization status
GET /twins/{twin_id}/research/{research_run_id}/finalization-status
Response: FinalizationStatusResponse

# List finalized claims
GET /twins/{twin_id}/research/{research_run_id}/finalized-claims
Response: FinalizedClaimsListResponse

# List consistency issues
GET /twins/{twin_id}/research/{research_run_id}/consistency-issues
Response: ConsistencyIssuesListResponse

# Resolve consistency issue
POST /twins/{twin_id}/research/{research_run_id}/consistency-issues/{issue_id}/resolve
Request: ResolveConsistencyIssueRequest
Response: ResolveConsistencyIssueResponse

# Manual override final status
POST /twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/finalize-override
Request: FinalizeOverrideRequest
Response: FinalizeOverrideResponse
```

### 3.5 Feature Flag

**Add to config:**
```python
phase_10_claim_finalization_disabled: bool = Field(default=False)
# Environment: DR_PHASE_10_CLAIM_FINALIZATION_DISABLED
```

---

## 4. Finalization Rules (MVP)

### Rule Priority (applied in order)

1. **Strong Agreement**: local=supported AND web=supported → **accepted**
2. **Strong Conflict**: local=conflicting OR web=conflicting → **rejected**
3. **Needs Review Flag**: local=needs_review OR web=needs_review → **needs_review**
4. **Single Source Success**: web=None AND local=supported → **accepted** (note: "local only")
5. **Status Mismatch**: local != web (neither None) → **needs_review** (note: "verification conflict")
6. **Insufficient Evidence**: local=insufficient_evidence AND (web=None OR web=insufficient_evidence) → **rejected**
7. **Default**: → **unresolved**

### Confidence Calculation

- Both sources available: `avg(local_confidence, web_confidence)`
- Local only: `local_confidence * 0.9` (slight penalty for no web verification)
- Manual override: override value

---

## 5. Consistency Detection Rules (MVP)

### Contradiction Detection

1. **Opposite Preferences**: "I prefer X" vs "I dislike X" / "I hate X"
2. **Opposite Beliefs**: "I believe X" vs "I don't believe X" / "X is false"
3. **Boundary Conflicts**: "I never do X" vs "I always do X"

### Duplicate Detection

1. **Near-Duplicate Claims**: Similar text (>80% similarity) with different IDs
2. **Same Source Different Status**: Same claim_text from same source with different statuses

### Confidence Mismatch Detection

1. **High vs Low**: One claim accepted with 0.9 confidence, similar claim rejected with 0.3 confidence

---

## 6. Test Plan

### Unit Tests
- Finalization rule engine (all rule combinations)
- Consistency checker (contradiction, duplicate, mismatch detection)
- Hash generation for deduplication

### Integration Tests
- Full finalization pipeline
- Consistency issue persistence and resolution
- Service orchestration

### Regression Tests
- Phase 8 local verification unchanged
- Phase 9 web verification unchanged
- Existing endpoints backward compatible

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Rule complexity | Keep rules simple and deterministic, document clearly |
| False positives in consistency | Allow easy dismiss, track override reasons |
| Performance with many claims | Batch processing, efficient queries |
| Data integrity | Separate tables, no mutation to Phase 8/9 |

---

## 8. STOP Confirmation

This plan covers **Phase 10 ONLY**. No Phase 11 implementation will be done.
