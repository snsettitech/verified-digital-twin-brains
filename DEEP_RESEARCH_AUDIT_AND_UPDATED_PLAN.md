# Deep Research System: Full Codebase Audit + Updated Execution Plan

> **Audit Date:** 2026-02-23  
> **Auditor:** Senior Staff Engineer + Principal Architect  
> **Status:** AUDIT COMPLETE - PLAN UPDATED  
> **Supersedes:** DEEP_RESEARCH_IMPLEMENTATION_PLAN.md (Phases 1A, 1B, 2 confirmed)  

---

## PART 1: CURRENT STATE AUDIT SUMMARY

### 1.1 VERIFIED IMPLEMENTED COMPONENTS

#### Phase 1A: Crawl Skeleton + Safety ✅ COMPLETE

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Crawl runs table | ✅ | Migration applied | `crawl_runs` with twin scoping |
| Crawl pages table | ✅ | Migration applied | `crawl_pages` metadata-only |
| URL canonicalizer | ✅ | `modules/url_canonicalizer.py` | 37 tests passing |
| Content hasher | ✅ | `modules/content_hasher.py` | SHA-256 with normalization |
| Fetch safety | ✅ | `modules/fetch_safety.py` | SSRF, content-type, size limits |
| Artifact store | ✅ | `modules/artifact_store.py` | Filesystem backend, S3-ready |
| Crawl endpoints | ✅ | `routers/crawl.py` | Feature-flag gated |
| Deep research config | ✅ | `modules/deep_research_config.py` | Feature flags centralized |

#### Phase 1B: Recrawl Idempotency ✅ COMPLETE

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Crawl repository | ✅ | `modules/crawl_repository.py` | 380 lines, full CRUD |
| Crawl manager | ✅ | `modules/crawl_manager.py` | Classification logic |
| Failure taxonomy | ✅ | `modules/crawl_failure_taxonomy.py` | 12 types, retry matrix |
| Canonical URL persistence | ✅ | DB column + index | `canonical_url`, `url_hash` |
| Version chaining | ✅ | DB column | `previous_page_id` |
| Changes endpoint | ✅ | `routers/crawl.py` | `/changes` returns diff stats |

#### Phase 2: Ingestion Bridge ✅ COMPLETE

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Crawl→Source bridge | ✅ | `modules/crawl_ingestion_bridge.py` | 15KB, full implementation |
| Versioned metadata | ✅ | `pinecone_adapter.py` | 7 new fields added |
| Tombstone filter | ✅ | `retrieval.py` | Default `is_current=True` filter |
| Chunk version manager | ✅ | `modules/chunk_version_manager.py` | Framework + stubs |
| Bridge tests | ✅ | `tests/test_crawl_ingestion_bridge.py` | 14 tests passing |
| Version manager tests | ✅ | `tests/test_chunk_version_manager.py` | 17 tests passing |

### 1.2 PARTIAL / STUBBED COMPONENTS

| Component | Status | Location | What's Missing |
|-----------|--------|----------|----------------|
| Crawl job processing | 🟡 STUB | `routers/crawl.py:209` | "TODO: enqueue crawl job" - no background processing |
| Actual crawl fetching | 🟡 STUB | `modules/web_crawler.py` | Skeleton v2, no Firecrawl integration |
| Tombstone operations | 🟡 STUB | `chunk_version_manager.py` | Metadata framework ready, vector updates stubbed |
| Source confirmation | 🔴 NOT BUILT | N/A | Needs identity confidence scoring |
| Research orchestration | 🔴 NOT BUILT | N/A | Research runs table exists in schema only |
| Bio generation | 🟡 EXISTS | `persona_link_compile.py` | Uses different flow, needs crawl integration |

### 1.3 NOT IMPLEMENTED (Phase 3+)

| Component | Status | Plan Location |
|-----------|--------|---------------|
| Research run persistence | 🔴 NOT BUILT | Phase 3.1 |
| Subquestion planner | 🔴 NOT BUILT | Phase 3.4 |
| Claim extractor | 🔴 NOT BUILT | Phase 4.1 |
| Claim classifier | 🔴 NOT BUILT | Phase 4.2 |
| Local verifier | 🔴 NOT BUILT | Phase 4.3 |
| Web verifier | 🔴 NOT BUILT | Phase 5 |
| Research synthesizer | 🔴 NOT BUILT | Phase 6.3 |
| Chat mode=deep_research | 🟡 STUB | `routers/chat.py` - needs integration |

### 1.4 SCHEMA AUDIT

**crawl_runs table:**
- ✅ All columns from migration present
- ✅ Indexes created
- ✅ `previous_crawl_id` for recrawl chain
- ⚠️ No `onboarding_session_id` (needed for onboarding flow)

**crawl_pages table:**
- ✅ All columns present
- ✅ `url_hash` index present
- ✅ `canonical_url` index present
- ⚠️ No `identity_confidence_score` (needed for source confirmation)
- ⚠️ No `confirmation_status` (pending/confirmed/rejected)

**Sources table (existing):**
- ✅ `crawl_id`, `crawl_page_id` in metadata JSONB
- ✅ `citation_url` for canonical URL
- ⚠️ No direct foreign key to crawl_pages (by design - loose coupling)

**Missing tables (needed for Phase 3):**
- 🔴 `research_runs` - defined in schemas.py only
- 🔴 `research_subquestions` - defined in schemas.py only
- 🔴 `research_claims` - not defined
- 🔴 `source_confirmations` - not defined (for onboarding confirmation)

---

## PART 2: DRIFT ANALYSIS

### 2.1 Plan vs Actual Drift

| Planned | Actual | Drift | Impact |
|---------|--------|-------|--------|
| Firecrawl integration (Phase 1A) | Skeleton only | 🔴 MAJOR | No actual HTTP fetching implemented |
| Research tables (Phase 3) | Schemas only | 🔴 MAJOR | No migrations applied |
| Job queue integration (Phase 3) | Partial | 🟡 MEDIUM | Job queue exists but no crawl job processor |
| Claim extraction (Phase 4) | Not started | 🟡 MEDIUM | Plan needs re-alignment to onboarding |
| Mind score integration | Exists separately | 🟡 MEDIUM | Training metrics module exists - needs hook |

### 2.2 Architecture Drift

**Expected:**
- Generic deep research engine with query-driven research runs

**Actual:**
- Onboarding-driven crawl system with identity context
- Research schemas exist but not integrated with onboarding flow
- Bio generation exists in `persona_link_compile.py` using different mechanism

**Resolution:** Rephase Phase 3+ as "Onboarding-Driven Research" rather than generic research engine.

### 2.3 Frontend/Backend Contract Drift

| Frontend Expectation | Backend Status | Risk |
|---------------------|----------------|------|
| `StepProfileLanding.tsx` calls `/persona/link-compile/*` | ✅ Works | Uses legacy flow |
| Onboarding source submission | 🟡 PARTIAL | Needs crawl trigger integration |
| Source confirmation UI | 🔴 MISSING | Needs new endpoint |
| Bio variant selection | ✅ Works | Uses persona system |
| Claim review | ✅ Works | Uses persona system |
| Mind score display | ✅ Works | Training metrics module |

---

## PART 3: RISKS / COMPATIBILITY ISSUES

### 3.1 CRITICAL RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| No actual crawl fetching | HIGH | Phase 1A needs Firecrawl integration before Phase 3 |
| Research tables not created | HIGH | Migration needed before Phase 3 implementation |
| Onboarding flow divergence | MEDIUM | Align Phase 3 with existing persona_link_compile flow |
| Import inconsistencies | MEDIUM | Mixed `backend.modules` vs `modules` imports need fixing |

### 3.2 COMPATIBILITY REQUIREMENTS

**MUST Preserve:**
1. Existing chat flow (no changes to `/chat` router behavior)
2. Existing ingestion pipeline (crawl bridge is additive)
3. Existing twin/profile APIs (onboarding integration must be additive)
4. Existing mind score calculation (training_metrics module)
5. Existing persona/bio system (persona_link_compile router)

**MUST Integrate With:**
1. `persona_link_compile.py` - for bio generation handoff
2. `training_metrics.py` - for mind score update trigger
3. `StepProfileLanding.tsx` - for source confirmation UI contract

---

## PART 4: UPDATED EXECUTION-READY PLAN

### Implementation Status Table

| Phase | Name | Status | Tests |
|-------|------|--------|-------|
| 1A | Crawl Skeleton + Safety | ✅ COMPLETE | 175 passing |
| 1B | Recrawl Idempotency | ✅ COMPLETE | 89 passing |
| 2 | Ingestion Bridge | ✅ COMPLETE | 40 passing |
| 3 | Onboarding Integration + Research Orchestration | 🔄 PLANNED | - |
| 4 | Source Confirmation + Identity Resolution | 🔄 PLANNED | - |
| 5 | Research Execution (Local + Web) | 🔄 PLANNED | - |
| 6 | Twin-Ready Handoff + Mind Score | 🔄 PLANNED | - |

### Revised Phase Breakdown

---

## PHASE 3: Onboarding Integration + Research Orchestration

**Goal:** Integrate crawl system with onboarding flow and establish research run foundation.

**Phase Gate:** All sub-phases must pass tests + integration verification before Phase 4.

---

### Phase 3.0: Prerequisite Fixes

**Before Phase 3 implementation:**

1. **Fix import inconsistencies**
   - Standardize all imports to `from modules.xxx` (remove `backend.modules`)
   - Files to fix: `crawl_repository.py`, `crawl_manager.py`, `crawl.py`

2. **Apply missing migration**
   - Create migration for `research_runs` table (schema already defined)
   - Create migration for `research_subquestions` table
   - Create migration for `onboarding_sessions` table (if not exists)

3. **Firecrawl integration stub**
   - Add Firecrawl client configuration
   - Create crawl job processor skeleton

**Acceptance Criteria:**
- [ ] All imports consistent
- [ ] All migrations applied cleanly
- [ ] No regression in existing 304 tests

---

### Phase 3.1: Onboarding Session Context

**Goal:** Link crawl runs to onboarding sessions with identity context.

**Files:**
- `modules/onboarding_context.py` (new)
- `routers/crawl.py` (modify)

**Implementation:**
```python
class OnboardingContext:
    """Context for onboarding-driven crawl."""
    full_name: str
    location: Optional[str]
    submitted_links: List[SubmittedLink]
    identity_confidence_threshold: float = 0.8
    
class SubmittedLink:
    url: str
    link_type: str  # linkedin, youtube, website, etc.
    claimed_identity: str  # How user describes this link
    confidence_score: Optional[float]  # Computed identity match
    confirmation_status: str  # pending/confirmed/rejected
```

**Changes:**
- Extend `CreateCrawlRequest` with optional `onboarding_session_id`
- Store identity context in crawl_runs.metadata
- Add `identity_confidence_score` to crawl_pages

**Acceptance Criteria:**
- [ ] Crawl can be created with onboarding context
- [ ] Identity context stored and retrievable
- [ ] 5 new tests passing

---

### Phase 3.2: Research Run Foundation

**Goal:** Create research run persistence layer.

**Files:**
- `modules/research_repository.py` (new)
- `database/migrations/migration_research_tables.sql` (new)

**Tables:**
```sql
-- research_runs (from schemas.py, now applied)
CREATE TABLE research_runs (
    id UUID PRIMARY KEY,
    twin_id UUID REFERENCES twins(id),
    crawl_id UUID REFERENCES crawl_runs(id),  -- Link to crawl
    onboarding_session_id UUID,  -- Link to onboarding
    status VARCHAR(20),  -- planning, running, awaiting_confirmation, completed, failed
    identity_context JSONB,  -- Full name, location, submitted links
    checkpoint_data JSONB,  -- Resume state
    created_at TIMESTAMPTZ
);

-- source_confirmations (new)
CREATE TABLE source_confirmations (
    id UUID PRIMARY KEY,
    research_run_id UUID,
    crawl_page_id UUID,
    url TEXT,
    identity_confidence_score FLOAT,
    confirmation_status VARCHAR(20),  -- pending, confirmed, rejected
    user_feedback TEXT,
    created_at TIMESTAMPTZ
);
```

**Acceptance Criteria:**
- [ ] Migrations apply cleanly
- [ ] Repository CRUD operations work
- [ ] 10 new tests passing

---

### Phase 3.3: Crawl Job Processor

**Goal:** Background processing of crawl jobs.

**Files:**
- `modules/crawl_job_processor.py` (new)
- `modules/web_crawler_v2.py` (enhance)

**Implementation:**
```python
async def process_crawl_job(job_id: str, crawl_id: str):
    """Process crawl in background worker."""
    # 1. Update status to 'running'
    # 2. Fetch each URL (Firecrawl integration)
    # 3. Classify each page (new/unchanged/changed)
    # 4. Store artifacts
    # 5. Trigger ingestion bridge
    # 6. Update status to 'completed' or 'awaiting_confirmation'
```

**Firecrawl Integration:**
- Add `FIRECRAWL_API_KEY` to config
- Create `modules/firecrawl_client.py` wrapper
- Implement fetch with safety checks

**Acceptance Criteria:**
- [ ] Crawl jobs process in background
- [ ] Firecrawl fetches URLs safely
- [ ] Classification logic applied
- [ ] Artifacts stored correctly
- [ ] 15 new tests passing

---

### Phase 3.4: Identity Confidence Scoring

**Goal:** Score how likely a crawled page matches the claimed identity.

**Files:**
- `modules/identity_confidence_scorer.py` (new)

**Algorithm:**
```python
def calculate_identity_confidence(
    page_content: str,
    page_metadata: dict,
    claimed_identity: dict  # full_name, location
) -> float:
    """
    Score 0.0-1.0 based on:
    - Name presence in content (0.3)
    - Name in title/meta (0.2)
    - Location presence (0.2)
    - URL match with name (0.15)
    - Profile indicators (0.15)
    """
```

**Acceptance Criteria:**
- [ ] Confidence scores computed for each page
- [ ] Scores stored in crawl_pages
- [ ] Configurable threshold (default 0.8)
- [ ] 10 new tests passing

---

### Phase 3.5: Source Confirmation Endpoint

**Goal:** API for user to confirm/reject ambiguous sources.

**Files:**
- `routers/crawl.py` (add endpoints)

**Endpoints:**
```python
@router.get("/twins/{twin_id}/crawls/{crawl_id}/pending-confirmations")
async def get_pending_confirmations(...):
    """Get pages needing user confirmation."""
    
@router.post("/twins/{twin_id}/crawls/{crawl_id}/confirmations/{confirmation_id}")
async def confirm_source(..., action: Literal["confirm", "reject"]):
    """User confirms or rejects a source."""
```

**Acceptance Criteria:**
- [ ] Endpoint returns pending confirmations
- [ ] Confirm action marks source for ingestion
- [ ] Reject action tombstones source
- [ ] Research run resumes after confirmations
- [ ] 8 new tests passing

---

## PHASE 4: Source Confirmation + Identity Resolution

### Phase 4.1: Confirmation Checkpoint

**Goal:** Pause/resume research run for source confirmation.

**Files:**
- `modules/research_orchestrator.py` (new)

**State Machine:**
```
planning → crawling → awaiting_confirmation → [user confirms] → ingesting → researching → completed
                                    ↓
                              [timeout] → completed (with warnings)
```

**Acceptance Criteria:**
- [ ] Run pauses when ambiguous sources found
- [ ] Run resumes after user confirmation
- [ ] Timeout handling (24h default)
- [ ] 10 new tests passing

---

### Phase 4.2: Confirmed Source Ingestion

**Goal:** Only ingest confirmed sources.

**Files:**
- `modules/crawl_ingestion_bridge.py` (modify)

**Change:**
- Add `confirmation_required` flag
- Skip ingestion for unconfirmed sources in onboarding flow
- Tombstone rejected sources

**Acceptance Criteria:**
- [ ] Only confirmed sources ingested
- [ ] Rejected sources tombstoned
- [ ] Mind score updated post-ingestion
- [ ] 5 new tests passing

---

## PHASE 5: Research Execution (Simplified for Onboarding)

**Note:** Full claim extraction + verification is Phase 5 in original plan. For onboarding MVP, we simplify to:

### Phase 5.1: Bio Generation Trigger

**Goal:** Trigger existing bio generation after crawl completion.

**Files:**
- Integrate with existing `persona_link_compile.py`

**Implementation:**
```python
# After crawl ingestion completes:
from modules.persona_link_compile import trigger_bio_generation

trigger_bio_generation(
    twin_id=twin_id,
    crawl_id=crawl_id,  # New parameter
    sources=confirmed_sources
)
```

**Acceptance Criteria:**
- [ ] Bio generation triggered after crawl
- [ ] Uses confirmed sources
- [ ] Bio variants stored correctly
- [ ] 5 new tests passing

---

### Phase 5.2: Research Summary Generation

**Goal:** Generate research summary for twin profile.

**Files:**
- `modules/research_synthesizer.py` (simplified)

**Output:**
```json
{
  "summary": "Brief bio from crawled sources",
  "source_count": 5,
  "confirmed_sources": [...],
  "key_topics": ["topic1", "topic2"],
  "confidence": "high"
}
```

**Acceptance Criteria:**
- [ ] Summary generated from sources
- [ ] Topics extracted
- [ ] Confidence scored
- [ ] 5 new tests passing

---

## PHASE 6: Twin-Ready Handoff + Mind Score

### Phase 6.1: Mind Score Integration

**Goal:** Update mind score after crawl ingestion.

**Files:**
- `modules/crawl_ingestion_bridge.py` (modify)

**Implementation:**
```python
from modules.training_metrics import update_twin_training_metrics

# After successful ingestion:
await update_twin_training_metrics(twin_id)
```

**Acceptance Criteria:**
- [ ] Mind score updated post-ingestion
- [ ] Words processed count accurate
- [ ] Questions answerable estimated
- [ ] 5 new tests passing

---

### Phase 6.2: Twin-Ready Status

**Goal:** Mark twin as ready when sufficient sources confirmed.

**Files:**
- `modules/twin_readiness.py` (new)

**Criteria:**
```python
is_twin_ready(twin_id):
    - mind_score >= threshold (default 30)
    - at least 1 bio variant generated
    - at least 1 confirmed source
    - no pending confirmations (or timeout passed)
```

**Acceptance Criteria:**
- [ ] Readiness check implemented
- [ ] Status stored in twin record
- [ ] Endpoint for readiness status
- [ ] 5 new tests passing

---

### Phase 6.3: Profile Page Integration

**Goal:** Frontend can display research results.

**Contract:**
```typescript
// GET /twins/{twin_id}/research-summary
interface ResearchSummary {
  status: 'in_progress' | 'awaiting_confirmation' | 'completed';
  sources: ConfirmedSource[];
  pendingConfirmations?: PendingConfirmation[];
  bioVariants: BioVariant[];
  mindScore: number;
  isReady: boolean;
}
```

**Acceptance Criteria:**
- [ ] Endpoint returns full summary
- [ ] Compatible with StepProfileLanding.tsx
- [ ] Polling mechanism documented
- [ ] 5 new tests passing

---

## PART 5: BLOCKING QUESTIONS

### Question 1: Firecrawl Integration Priority

**Question:** Should we implement Firecrawl integration in Phase 3.3, or use the existing DumplingAI integration that already works for LinkedIn/YouTube?

**Options:**
- **A:** Use DumplingAI (faster, already integrated)
- **B:** Implement Firecrawl (more generic, matches original plan)

**Impact:**
- A: Unblocks Phase 3 faster, uses proven infrastructure
- B: Stays true to original architecture, more flexible

**Default Recommendation:** **A** - Use DumplingAI for now, migrate to Firecrawl later if needed.

**What is blocked:** Nothing - proceed with A

---

### Question 2: Source Confirmation UI

**Question:** Should we build a new source confirmation UI, or integrate into existing StepProfileLanding.tsx "Add More Sources" flow?

**Options:**
- **A:** Extend StepProfileLanding.tsx with confirmation step
- **B:** Build separate /onboarding/confirm-sources page

**Impact:**
- A: Faster integration, uses existing UI patterns
- B: Cleaner separation, more complex

**Default Recommendation:** **A** - Extend existing component.

**What is blocked:** Nothing - proceed with A

---

### Question 3: Bio Generation Integration

**Question:** Should crawl-based bio generation replace or augment existing persona_link_compile flow?

**Options:**
- **A:** Augment - crawl adds sources to existing flow
- **B:** Replace - crawl becomes primary source for bio

**Impact:**
- A: Safer, backward compatible
- B: Simpler long-term, riskier transition

**Default Recommendation:** **A** - Augment existing flow.

**What is blocked:** Nothing - proceed with A

---

## PART 6: EXECUTION ROADMAP

### Immediate (This Week)

1. Fix import inconsistencies (2 hours)
2. Apply research tables migration (2 hours)
3. Build onboarding context module (4 hours)
4. Build identity confidence scorer (6 hours)

**Sub-phases:** 3.0, 3.1, 3.4

### Short Term (Next 2 Weeks)

1. Build research repository (4 hours)
2. Build crawl job processor (8 hours)
3. Integrate DumplingAI for fetching (6 hours)
4. Build confirmation endpoints (6 hours)

**Sub-phases:** 3.2, 3.3, 3.5, 4.1

### Medium Term (Weeks 3-4)

1. Build research orchestrator with checkpointing (8 hours)
2. Integrate with persona_link_compile (4 hours)
3. Build simplified research synthesizer (6 hours)
4. Build twin readiness module (4 hours)

**Sub-phases:** 4.2, 5.1, 5.2, 6.1, 6.2

### Final Integration (Week 5)

1. Frontend integration contract (6 hours)
2. End-to-end testing (8 hours)
3. Regression testing (4 hours)
4. Documentation (4 hours)

**Sub-phases:** 6.3 + integration

---

## PART 7: TEST STRATEGY

### Unit Tests per Sub-phase
- Each module: min 10 tests
- Each endpoint: min 5 tests
- Repository layer: min 10 tests

### Integration Tests
- Crawl → Confirmation → Ingestion → Bio: 5 tests
- Onboarding E2E flow: 3 tests
- Mind score update: 3 tests

### Regression Tests
- Existing 304 tests must all pass
- Chat functionality unchanged
- Existing ingestion unchanged
- Profile APIs unchanged

---

## APPENDIX: REVISION HISTORY

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 1.0 | Initial audit and plan update |

---

**END OF PLAN**

**STOP HERE - NO IMPLEMENTATION YET**

Awaiting confirmation on blocking questions before proceeding.
