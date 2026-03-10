# Phase 9: Web Verification Enrichment - Audit & Implementation Plan

## 1. Phase 9 Compatibility Audit

### Phase 8 Infrastructure (Existing)

#### Database Schema
- **research_claims** table: Stores atomic claims with Phase 8 local verification
  - Fields: `id`, `research_run_id`, `twin_id`, `claim_text`, `claim_type`, `verification_status`, `confidence`, `evidence_quotes`
  - `verification_status`: pending, supported, insufficient_evidence, conflicting, needs_review
  - `claim_type`: preference, belief, heuristic, value, experience, boundary, uncertain
  
- **research_claim_enrichment** table: Tracks Phase 8 enrichment progress
  - Fields: `research_run_id`, `twin_id`, `status`, counts by status, timestamps

#### Service Layer
- **ResearchClaimExtractor** (`research_claim_extractor.py`): Extracts claims from confirmed sources
- **ClaimVerifier** (`research_claim_verifier.py`): Local verification using TF-IDF similarity
- **ResearchClaimService** (`research_claim_service.py`): Orchestrates Phase 8 enrichment

#### API Endpoints
- `POST /twins/{twin_id}/research/{research_run_id}/continue-claims`
- `GET /twins/{twin_id}/research/{research_run_id}/claims-status`
- `GET /twins/{twin_id}/research/{research_run_id}/claims`
- `POST /twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve`

#### State Machine
- Current terminal: `COMPLETED` (Phase 5)
- Phase 8 extension: `COMPLETED` → `CLAIMS_ENRICHMENT` → `CLAIMS_COMPLETED`
- `CLAIMS_COMPLETED` is Phase 8 terminal state

#### Feature Flags
- `DEEP_RESEARCH_ENABLED` - Master switch
- `DEEP_RESEARCH_GLOBAL_DISABLE` - Emergency kill switch
- `DR_PHASE_8_CLAIMS_DISABLED` - Phase 8 specific

### Reusable Components for Phase 9

1. **Firecrawl Client** (`firecrawl_client.py`)
   - `scrape_with_retry(url)` - Fetch and extract content
   - Circuit breaker, retry logic, error mapping
   - Content quality assessment (FULL, PARTIAL, BLOCKED, MANUAL_NEEDED)

2. **Search Provider Config** (`deep_research_config.py`)
   - `SearchProviderConfig` - Exa, Brave, Serper support
   - `CLAIM_CLASS_TAXONOMY` - Web verification eligibility rules
   - `is_web_verification_eligible()` - Policy function

3. **Failure Taxonomy** (`crawl_failure_taxonomy.py`)
   - Error classification and retry logic
   - Can be extended for web verification errors

### Attachment Points for Phase 9

1. **Database**: New table `research_claim_web_verifications` linked to `research_claims`
2. **State Machine**: Extend from `CLAIMS_COMPLETED` → `WEB_VERIFICATION` → `WEB_VERIFIED`
3. **Service**: New `ResearchClaimWebVerificationService` orchestrator
4. **API**: New endpoints under existing `/twins/{twin_id}/research/{research_run_id}/` prefix

---

## 2. Phase 9 Implementation Plan

### Phase 9 Goal
Add web verification enrichment for Phase 8 claims using public web sources as external validation, while preserving Phase 8 local verification as-is.

### Architecture Principles
1. **Additive Only**: Phase 9 does NOT replace Phase 8
2. **Optional Step**: Runs after `CLAIMS_COMPLETED`, which remains a valid terminal state
3. **Separate Storage**: Web verification in separate tables, no mutation to Phase 8 fields
4. **Provider Abstraction**: Mockable web search interface
5. **Idempotent**: Safe to retry without duplication

---

## 3. Implementation Details

### 3.1 Database Migration
**File**: `backend/database/migrations/migration_phase_9_web_verification.sql`

```sql
-- Web verification status for claims
CREATE TABLE IF NOT EXISTS research_claim_web_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    -- Web verification fields (separate from Phase 8 local verification)
    web_verification_status VARCHAR(50) DEFAULT 'pending',
    web_verification_confidence FLOAT DEFAULT 0.0,
    web_verification_notes TEXT,
    
    -- Evidence summary
    sources_searched INTEGER DEFAULT 0,
    sources_found INTEGER DEFAULT 0,
    supporting_evidence_count INTEGER DEFAULT 0,
    conflicting_evidence_count INTEGER DEFAULT 0,
    
    -- Search metadata
    search_query TEXT,
    search_provider VARCHAR(50),
    
    -- Timestamps
    web_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Web evidence items (supporting or conflicting)
CREATE TABLE IF NOT EXISTS research_claim_web_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id UUID NOT NULL REFERENCES research_claim_web_verifications(id) ON DELETE CASCADE,
    claim_id UUID NOT NULL REFERENCES research_claims(id) ON DELETE CASCADE,
    
    -- Evidence details
    source_url TEXT NOT NULL,
    source_title TEXT,
    source_snippet TEXT,
    extracted_quote TEXT,
    relevance_score FLOAT,
    evidence_type VARCHAR(20), -- 'supporting' | 'conflicting' | 'neutral'
    
    -- Quality metrics
    content_quality VARCHAR(20), -- 'full' | 'partial' | 'blocked'
    domain_tier INTEGER, -- 1, 2, 3 for source quality
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Web verification run tracking (per research run)
CREATE TABLE IF NOT EXISTS research_web_verification_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    
    status VARCHAR(50) DEFAULT 'pending', -- pending, running, completed, failed
    total_claims INTEGER DEFAULT 0,
    verified_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_web_verifications_claim ON research_claim_web_verifications(claim_id);
CREATE INDEX IF NOT EXISTS idx_web_verifications_run ON research_claim_web_verifications(research_run_id);
CREATE INDEX IF NOT EXISTS idx_web_verifications_status ON research_claim_web_verifications(web_verification_status);
CREATE INDEX IF NOT EXISTS idx_web_evidence_verification ON research_claim_web_evidence(verification_id);
CREATE INDEX IF NOT EXISTS idx_web_evidence_claim ON research_claim_web_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_web_verification_runs_run ON research_web_verification_runs(research_run_id);
```

### 3.2 Backend Modules

#### Module 1: Web Search Provider
**File**: `backend/modules/research_claim_web_search.py`

**Responsibilities**:
- Abstract web search interface
- Provider implementations (Exa, Brave, Serper)
- Return candidate URLs/snippets for a claim
- Deterministic mocks for testing

**Key Classes**:
```python
class WebSearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, num_results: int = 5) -> List[SearchResult]

class ExaSearchProvider(WebSearchProvider)
class BraveSearchProvider(WebSearchProvider)
class MockSearchProvider(WebSearchProvider)  # For tests
```

#### Module 2: Web Verifier
**File**: `backend/modules/research_claim_web_verifier.py`

**Responsibilities**:
- Fetch candidate pages via Firecrawl client
- Score support/conflict against claim using LLM + similarity
- Deduplicate evidence URLs
- Output structured evidence + decision

**Key Classes**:
```python
@dataclass
class WebVerificationResult:
    claim_id: str
    status: WebVerificationStatus  # supported, conflicting, insufficient_evidence, needs_review, blocked, error
    confidence: float
    evidence: List[WebEvidenceItem]
    notes: str

class ClaimWebVerifier:
    async def verify_claim(
        self,
        claim: ResearchClaim,
        search_provider: WebSearchProvider,
        max_results: int = 5
    ) -> WebVerificationResult
```

**Web Verification Statuses**:
- `pending` - Not yet verified
- `supported` - Web evidence supports claim
- `conflicting` - Web evidence contradicts claim
- `insufficient_evidence` - No relevant web evidence found
- `needs_review` - Ambiguous evidence, needs manual review
- `blocked` - Access blocked (robots, gating)
- `error` - Verification error

#### Module 3: Web Verification Service
**File**: `backend/modules/research_claim_web_verification_service.py`

**Responsibilities**:
- Orchestrate search → fetch → verify → persist for research_run_id
- Idempotent reruns and safe retries
- Store summary stats
- Filter claims by eligibility (using taxonomy)

**Key Classes**:
```python
class WebVerificationSummary:
    research_run_id: str
    status: WebVerificationRunStatus
    total_claims: int
    verified_count: int
    by_status: Dict[str, int]

class ResearchClaimWebVerificationService:
    async def verify_research_run(
        self,
        research_run_id: str,
        twin_id: str,
        search_provider: Optional[WebSearchProvider] = None
    ) -> WebVerificationSummary
    
    async def get_verification_status(
        self,
        research_run_id: str,
        twin_id: str
    ) -> Optional[WebVerificationSummary]
    
    async def list_claims_with_verification(
        self,
        research_run_id: str,
        twin_id: str,
        include_web: bool = True
    ) -> List[ClaimWithVerification]
```

### 3.3 Orchestrator Integration

**File**: `backend/modules/research_orchestrator.py`

**Additions**:
```python
class ResearchRunStatus(str, Enum):
    # ... existing phases 1-8 ...
    CLAIMS_COMPLETED = "claims_completed"  # Phase 8 terminal (now non-terminal for Phase 9)
    WEB_VERIFICATION = "web_verification"  # Phase 9
    WEB_VERIFIED = "web_verified"          # Phase 9 terminal

# Valid transitions
VALID_TRANSITIONS[ResearchRunStatus.CLAIMS_COMPLETED].add(ResearchRunStatus.WEB_VERIFICATION)
VALID_TRANSITIONS[ResearchRunStatus.WEB_VERIFICATION] = {
    ResearchRunStatus.WEB_VERIFIED,
    ResearchRunStatus.FAILED,
    ResearchRunStatus.WEB_VERIFICATION,  # Self for idempotency
}
```

### 3.4 API Router

**File**: `backend/routers/research_claims.py` (extend existing)

**New Endpoints**:
```python
# Continue to web verification (idempotent)
POST /twins/{twin_id}/research/{research_run_id}/continue-web-verification
Response: WebVerificationResponse

# Get web verification status
GET /twins/{twin_id}/research/{research_run_id}/web-verification-status
Response: WebVerificationStatusResponse

# List claims with both local and web verification
GET /twins/{twin_id}/research/{research_run_id}/claims?include_web=true
Response: ClaimsListResponse (extended with web_verification field)

# List web evidence for a claim
GET /twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/web-evidence
Response: WebEvidenceListResponse

# Manually resolve web verification
POST /twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve-web
Request: ResolveWebVerificationRequest
Response: ResolveWebVerificationResponse
```

### 3.5 Feature Flags

**File**: `backend/modules/deep_research_config.py`

**Addition**:
```python
class DeepResearchConfig(BaseModel):
    # ... existing ...
    phase_8_claims_disabled: bool = Field(default=False)
    phase_9_web_verification_disabled: bool = Field(default=False)  # NEW

    @classmethod
    def from_env(cls) -> "DeepResearchConfig":
        return cls(
            # ... existing ...
            phase_9_web_verification_disabled=os.getenv(
                "DR_PHASE_9_WEB_VERIFICATION_DISABLED", "false"
            ).lower() == "true",
        )
```

**Environment Variable**: `DR_PHASE_9_WEB_VERIFICATION_DISABLED`

---

## 4. Test Plan

### Unit Tests
**File**: `backend/tests/test_research_claim_web_verification.py`

```python
# Web Search Provider Tests
test_exa_provider_search
test_brave_provider_search
test_mock_provider_for_tests

# Web Verifier Tests
test_verify_claim_with_supporting_evidence
test_verify_claim_with_conflicting_evidence
test_verify_claim_no_evidence
test_verify_claim_blocked_content
test_dedup_evidence_urls

# Service Tests
test_verify_research_run_idempotent
test_filter_eligible_claims
test_persist_verification_results
test_get_verification_status
```

### Integration Tests
```python
test_full_web_verification_pipeline
test_phase_8_claims_preserved
test_state_machine_transitions
test_api_endpoints_contract
```

### Regression Tests
```python
test_phase_8_local_verification_unchanged
test_claims_completed_still_terminal_when_phase9_disabled
test_existing_claims_endpoints_backward_compatible
```

---

## 5. File Checklist

### New Files
- [ ] `backend/modules/research_claim_web_search.py`
- [ ] `backend/modules/research_claim_web_verifier.py`
- [ ] `backend/modules/research_claim_web_verification_service.py`
- [ ] `backend/database/migrations/migration_phase_9_web_verification.sql`
- [ ] `backend/tests/test_research_claim_web_verification.py`

### Modified Files
- [ ] `backend/modules/deep_research_config.py` - Add phase_9 flag
- [ ] `backend/modules/research_orchestrator.py` - Add WEB_VERIFICATION states
- [ ] `backend/routers/research_claims.py` - Add web verification endpoints
- [ ] `backend/main.py` - Ensure router registration (if needed)

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Phase 8 local verification broken | Separate tables, don't mutate existing fields |
| CLAIMS_COMPLETED no longer terminal | Keep as terminal when Phase 9 disabled |
| Search API rate limits | Configurable limits, circuit breaker, retry logic |
| Firecrawl fetch failures | Reuse existing error taxonomy, quality assessment |
| Evidence URL duplication | Hash-based dedup in verifier |
| LLM verification cost | Configurable max_results, similarity pre-filtering |

---

## 7. Deferred to Phase 10+

- Deep claim reasoning beyond evidence-based support/conflict
- Broad analytics dashboard
- Automatic claim resolution based on web verification
- Multi-hop web verification (following links)
- Real-time web verification during claim extraction
- Cross-claim consistency checking
- Historical web verification tracking (snapshots)

---

## 8. STOP Confirmation

This plan covers **Phase 9 ONLY**. No Phase 10 implementation will be done.

**Phase 9 Boundaries**:
- ✅ Web verification enrichment for existing Phase 8 claims
- ✅ External web search + fetch + verify
- ✅ Local verification (Phase 8) preserved
- ✅ Optional post-claims step
- ❌ No Phase 10 work (cross-claim analysis, dashboards, etc.)
- ❌ No deployment changes
- ❌ No chat/standard ingestion changes
