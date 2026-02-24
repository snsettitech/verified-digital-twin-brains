# Firecrawl-Only Deep Research Implementation Plan

> **Version:** 2.0  
> **Date:** 2026-02-23  
> **Supersedes:** DEEP_RESEARCH_AUDIT_AND_UPDATED_PLAN.md  
> **Architecture:** Firecrawl-only for production crawling (MCP allowed for dev)  

---

## A) CURRENT-STATE COMPATIBILITY AUDIT

### A.1 VERIFIED SAFE TO PRESERVE

| Component | Status | Compatibility Notes |
|-----------|--------|---------------------|
| `routers/chat.py` | ✅ SAFE | No crawl/research dependencies; additive integration only |
| `routers/ingestion.py` | ✅ SAFE | Existing pipeline unchanged; crawl bridge is additive |
| `routers/twins.py` | ✅ SAFE | Mind score integration via hooks, not breaking changes |
| `routers/persona_link_compile.py` | ✅ SAFE | Bio generation will be triggered via additive hook |
| `modules/training_metrics.py` | ✅ SAFE | Update hook called post-ingestion; no signature changes |
| `modules/crawl_*.py` (Phases 1A-2) | ✅ SAFE | Foundation complete; Phase 3+ builds on top |
| `modules/web_crawler.py` | ✅ PARTIAL | Firecrawl client exists but needs error mapping + config refinement |
| `crawl_runs` table | ✅ SAFE | Schema stable; add `onboarding_session_id` optional FK |
| `crawl_pages` table | ✅ SAFE | Add `identity_confidence_score` + `confirmation_status` columns |
| Tombstone retrieval filter | ✅ SAFE | Default `is_current=True` preserved; no changes needed |
| Recrawl idempotency | ✅ SAFE | `canonical_url` + `content_hash` logic preserved |

### A.2 REQUIRES ADAPTATION

| Component | Current State | Required Change |
|-----------|---------------|-----------------|
| `modules/web_crawler.py` | Basic Firecrawl wrapper | Add error mapping to failure taxonomy, retry logic, config integration |
| `modules/deep_research_config.py` | Safety + limits config | Add Firecrawl-specific config section |
| `crawl_ingestion_bridge.py` | Phase 2 complete | Add identity confidence check + confirmation gate |
| Job queue | Generic job processor | Add `crawl` job type handler |

### A.3 MISSING (TO BUILD)

| Component | Purpose |
|-----------|---------|
| `modules/firecrawl_client.py` | Dedicated Firecrawl client wrapper with retry/circuit breaker |
| `modules/identity_confidence_scorer.py` | Score identity match between page content and claimed identity |
| `modules/research_orchestrator.py` | Onboarding-driven research run lifecycle + checkpointing |
| `modules/source_confirmation.py` | Confirmation state management + pause/resume logic |
| `modules/crawl_job_processor.py` | Background job processor for crawl execution |
| Research tables migrations | `research_runs`, `research_subquestions`, `source_confirmations` |

---

## B) FIRECRAWL-ONLY ARCHITECTURE DELTA

### B.1 Changes from Previous Plan

| Aspect | Previous Plan | Firecrawl-Only Plan |
|--------|---------------|---------------------|
| **Primary crawler** | Firecrawl (planned) + DumplingAI fallback | Firecrawl ONLY |
| **YouTube/social** | DumplingAI extraction | Firecrawl scrape with quality check; insufficient quality → manual confirmation path |
| **Error handling** | Generic HTTP errors | Firecrawl-specific error mapping to existing failure taxonomy |
| **MCP usage** | Not specified | Allowed for dev/testing/manual workflows ONLY |
| **Runtime transport** | Direct API calls | Dedicated `firecrawl_client.py` wrapper module |
| **Source strategy** | Unified | Matrix-based by source type (see B.2) |

### B.2 Source Strategy Matrix

| Source Type | Firecrawl Strategy | Identity Confidence | Fallback on Low Quality |
|-------------|-------------------|---------------------|------------------------|
| **Website root URL** | `crawl_url()` with `limit` + `maxDepth` | Aggregate across pages | Confirmation required if < threshold |
| **Single article/page** | `scrape_url()` with markdown format | Single page analysis | Confirmation required if < threshold |
| **LinkedIn profile** | `scrape_url()` with extraction hints | Name + title matching | If blocked/gated → manual upload path |
| **YouTube video** | `scrape_url()` for description/comments | Channel name + title match | If transcript unavailable → mark partial |
| **Twitter/X thread** | `scrape_url()` | Handle matching | If blocked → manual upload path |
| **Social (TikTok/Insta)** | `scrape_url()` | Handle/username matching | Often blocked; expect manual path |

**Quality Thresholds:**
- Identity confidence ≥ 0.8: Auto-confirm
- Identity confidence 0.5-0.8: Pending confirmation
- Identity confidence < 0.5: Auto-reject (tombstone)
- Firecrawl blocked/gating: Mark as `needs_manual_source`

### B.3 Firecrawl Error Mapping to Failure Taxonomy

| Firecrawl Error | Mapped FailureType | Retryable | Notes |
|-----------------|-------------------|-----------|-------|
| `429 Too Many Requests` | `RATE_LIMIT` | ✅ Yes | Exponential backoff |
| `403 Forbidden` | `AUTH` / `GATING` | ❌ No | Bot protection detected |
| `5xx Server Error` | `UNAVAILABLE` | ✅ Yes | Upstream failure |
| Timeout | `TIMEOUT` | ✅ Yes | Increase timeout, retry |
| DNS resolution failure | `NETWORK` | ✅ Yes | Transient network issue |
| SSL/TLS error | `NETWORK` | ✅ Yes | Certificate issue |
| Content too large | `SIZE_EXCEEDED` | ❌ No | Hard limit exceeded |
| Parse failure | `PARSER_FAIL` | ❌ No | Content structure issue |
| Robots.txt blocked | `GATING` | ❌ No | Policy restriction |

---

## C) UPDATED PHASE-BY-PHASE PLAN (PHASES 3–6)

### PHASE 3.0: Firecrawl Integration Foundation

**Goal:** Production-ready Firecrawl client with proper error handling and config.

#### 3.0.1 Firecrawl Client Module

**File:** `modules/firecrawl_client.py` (NEW)

```python
class FirecrawlClient:
    """
    Production Firecrawl client wrapper.
    - Retry with exponential backoff
    - Circuit breaker pattern
    - Error mapping to failure taxonomy
    - Concurrency limiting
    """
    
    def __init__(self, config: FirecrawlConfig):
        self.app = FirecrawlApp(api_key=config.api_key)
        self.config = config
        self.circuit_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.failure_count = 0
        
    async def scrape_with_retry(
        self, 
        url: str, 
        formats: List[str] = None,
        max_retries: int = 3
    ) -> FirecrawlResult:
        """Scrape with retry logic and error mapping."""
        
    async def crawl_with_polling(
        self,
        url: str,
        limit: int = 10,
        max_depth: int = 2,
        poll_interval: int = 5
    ) -> CrawlResult:
        """Start crawl and poll for completion."""
        
    def _map_error_to_taxonomy(self, error: Exception) -> FailureType:
        """Map Firecrawl error to existing failure taxonomy."""
```

**Config additions to `deep_research_config.py`:**
```python
class FirecrawlConfig(BaseModel):
    api_key: str
    base_url: Optional[str] = "https://api.firecrawl.dev"
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    max_concurrent: int = 5  # Per-crawl limit
    
    # Source-type specific settings
    website_crawl_limit: int = 50
    website_max_depth: int = 3
    scrape_formats: List[str] = ["markdown", "html"]
```

**Environment variables:**
```bash
FIRECRAWL_API_KEY=fc-...
FIRECRAWL_TIMEOUT_SECONDS=60
FIRECRAWL_MAX_RETRIES=3
FIRECRAWL_MAX_CONCURRENT=5
```

#### 3.0.2 Import Standardization Fix

**Files to fix:**
- `routers/crawl.py` lines 18-19, 447, 549: Change `backend.modules` → `modules`
- `modules/crawl_repository.py` line 42: Change `backend.modules` → `modules`
- `modules/web_crawler.py` lines 21-31: Change `backend.modules` → `modules`

#### 3.0.3 Database Migrations

**File:** `migrations/migration_phase3_research_tables.sql`

```sql
-- research_runs table
CREATE TABLE IF NOT EXISTS research_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    crawl_id UUID REFERENCES crawl_runs(id),  -- Link to crawl
    onboarding_session_id UUID,  -- Optional link to onboarding
    
    -- Identity context from onboarding
    claimed_identity JSONB DEFAULT '{}',  -- {full_name, location, links[]}
    
    -- Status: planning, crawling, awaiting_confirmation, processing, completed, failed
    status VARCHAR(30) NOT NULL DEFAULT 'planning',
    
    -- Checkpoint for resume
    checkpoint_data JSONB DEFAULT '{}',
    
    -- Timestamps
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- research_subquestions table
CREATE TABLE IF NOT EXISTS research_subquestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    sequence_number INT NOT NULL,
    question_text TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'planned',  -- planned, researching, completed, failed
    query_used TEXT,
    
    -- Results
    claims_extracted INT DEFAULT 0,
    claims_verified INT DEFAULT 0,
    synthesis_text TEXT,
    
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- source_confirmations table (for onboarding confirmation gate)
CREATE TABLE IF NOT EXISTS source_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    crawl_page_id UUID REFERENCES crawl_pages(id),
    
    -- Source info
    url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT,
    snippet TEXT,
    
    -- Identity matching
    identity_confidence_score FLOAT,
    identity_match_details JSONB,  -- {name_found: bool, location_found: bool, ...}
    
    -- Confirmation state: pending, confirmed, rejected, auto_confirmed, auto_rejected
    confirmation_status VARCHAR(20) DEFAULT 'pending',
    
    -- User feedback
    user_feedback TEXT,
    confirmed_by UUID,
    confirmed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_research_runs_twin_id ON research_runs(twin_id);
CREATE INDEX idx_research_runs_status ON research_runs(status);
CREATE INDEX idx_research_runs_crawl_id ON research_runs(crawl_id);
CREATE INDEX idx_source_confirmations_research_run_id ON source_confirmations(research_run_id);
CREATE INDEX idx_source_confirmations_status ON source_confirmations(confirmation_status);

-- Add columns to crawl_pages
ALTER TABLE crawl_pages 
    ADD COLUMN IF NOT EXISTS identity_confidence_score FLOAT,
    ADD COLUMN IF NOT EXISTS confirmation_status VARCHAR(20) DEFAULT 'pending';

-- Add column to crawl_runs for onboarding link
ALTER TABLE crawl_runs 
    ADD COLUMN IF NOT EXISTS onboarding_session_id UUID;
```

**Acceptance Criteria:**
- [ ] `modules/firecrawl_client.py` created with retry + circuit breaker
- [ ] All imports standardized to `modules.` (no `backend.modules`)
- [ ] Migrations apply cleanly to dev database
- [ ] Firecrawl config loads from environment
- [ ] Error mapping unit tests: 10 tests passing
- [ ] No regression in 304 existing tests

---

### PHASE 3.1: Identity Confidence Scorer

**Goal:** Score how well a crawled page matches the claimed identity.

**File:** `modules/identity_confidence_scorer.py` (NEW)

```python
class IdentityConfidenceScorer:
    """
    Score identity match between crawled content and claimed identity.
    
    Algorithm:
    - Name presence in title (0.25)
    - Name presence in content (0.20)
    - Location presence (0.15)
    - URL matching name (0.15)
    - Social handle matching (0.15)
    - Profile indicators (0.10)
    """
    
    def score_page(
        self,
        page_content: str,
        page_metadata: Dict[str, Any],
        claimed_identity: Dict[str, Any],  # {full_name, location, links[]}
    ) -> IdentityScore:
        """
        Returns:
            IdentityScore: {score: 0.0-1.0, details: {...}, confidence_level: str}
        """
```

**Integration point:**
- Called in `crawl_job_processor.py` after each page is fetched
- Score stored in `crawl_pages.identity_confidence_score`
- Details stored in metadata JSONB

**Acceptance Criteria:**
- [ ] Name matching handles variations (full name, first name, last name)
- [ ] Location matching is fuzzy (handles "SF" vs "San Francisco")
- [ ] URL slug matching (e.g., `/in/john-doe` matches "John Doe")
- [ ] Score thresholds: ≥0.8 high, 0.5-0.8 medium, <0.5 low
- [ ] 15 unit tests passing

---

### PHASE 3.2: Crawl Job Processor

**Goal:** Background job processor that executes crawls using Firecrawl.

**File:** `modules/crawl_job_processor.py` (NEW)

```python
async def process_crawl_job(job_id: str, crawl_id: str, twin_id: str):
    """
    Process a crawl job end-to-end:
    1. Fetch crawl config from DB
    2. Determine source strategy (crawl vs scrape)
    3. Execute Firecrawl operations with retry
    4. Classify pages (new/unchanged/changed)
    5. Score identity confidence
    6. Create source confirmations for ambiguous pages
    7. Update crawl status
    """

class SourceStrategy:
    """Determine Firecrawl strategy based on URL type."""
    
    @staticmethod
    def get_strategy(url: str) -> Strategy:
        """
        Returns:
            CRAWL: For website root URLs (discover subpages)
            SCRAPE: For single article/page URLs
            SOCIAL: For social profiles (LinkedIn, Twitter, etc.)
        """
```

**Source Strategy Implementation:**

```python
SOURCE_STRATEGIES = {
    # Website roots → Crawl
    "website_root": {
        "pattern": r"^https?://[^/]+/?$",
        "firecrawl_method": "crawl_url",
        "params": {"limit": 50, "maxDepth": 3},
    },
    # Articles/pages → Scrape
    "article": {
        "pattern": r"^https?://.+/.*\.(html|md|txt)$|^https?://.+/.*[/-].+$",
        "firecrawl_method": "scrape_url",
        "params": {"formats": ["markdown", "html"]},
    },
    # LinkedIn → Scrape with special handling
    "linkedin": {
        "pattern": r"linkedin\.com/in/",
        "firecrawl_method": "scrape_url",
        "params": {"formats": ["markdown"]},
        "expect_gating": True,
    },
    # YouTube → Scrape (description/comments only, not transcript)
    "youtube": {
        "pattern": r"youtube\.com/watch|youtu\.be/",
        "firecrawl_method": "scrape_url",
        "params": {"formats": ["markdown"]},
        "note": "Video content not extracted; description only",
    },
    # Twitter/X → Scrape
    "twitter": {
        "pattern": r"twitter\.com/|x\.com/",
        "firecrawl_method": "scrape_url",
        "params": {"formats": ["markdown"]},
        "expect_gating": True,
    },
}
```

**Acceptance Criteria:**
- [ ] Job processor handles all source types correctly
- [ ] Firecrawl errors mapped to taxonomy
- [ ] Identity confidence scored for each page
- [ ] Pages classified (new/unchanged/changed)
- [ ] Artifacts stored correctly
- [ ] 15 unit tests + 5 integration tests passing

---

### PHASE 3.3: Source Confirmation System

**Goal:** Pause/resume mechanism for user confirmation of ambiguous sources.

**File:** `modules/source_confirmation.py` (NEW)

```python
class SourceConfirmationManager:
    """
    Manage source confirmation lifecycle.
    
    State machine:
    pending → confirmed → ingested
           → rejected → tombstoned
           → auto_confirmed (high confidence)
           → auto_rejected (low confidence)
    """
    
    async def create_confirmations_for_crawl(
        self,
        crawl_id: str,
        research_run_id: str,
        auto_confirm_threshold: float = 0.8,
        auto_reject_threshold: float = 0.5,
    ) -> ConfirmationSummary:
        """
        Create confirmation records for all crawled pages.
        High confidence: auto-confirm
        Low confidence: auto-reject  
        Medium: pending user confirmation
        """
        
    async def confirm_source(
        self,
        confirmation_id: str,
        user_id: str,
        action: Literal["confirm", "reject"],
        feedback: Optional[str] = None,
    ) -> SourceConfirmation:
        """User confirms or rejects a source."""
        
    async def check_all_confirmed(
        self,
        research_run_id: str,
    ) -> bool:
        """Check if all sources have been resolved (no pending)."""
```

**API Endpoints (add to `routers/crawl.py`):**

```python
@router.get("/twins/{twin_id}/research/{research_run_id}/pending-confirmations")
async def get_pending_confirmations(...):
    """Get all sources needing user confirmation."""
    
@router.post("/twins/{twin_id}/research/{research_run_id}/confirmations/{confirmation_id}")
async def resolve_confirmation(
    action: Literal["confirm", "reject"],
    feedback: Optional[str] = None,
):
    """Confirm or reject a source."""
    
@router.post("/twins/{twin_id}/research/{research_run_id}/bulk-confirm")
async def bulk_confirm_sources(
    confirmation_ids: List[str],
    action: Literal["confirm", "reject"],
):
    """Bulk confirm/reject multiple sources."""
```

**Frontend Contract:**

```typescript
// GET /twins/{twin_id}/research/{research_run_id}/pending-confirmations
interface PendingConfirmation {
  id: string;
  url: string;
  canonical_url: string;
  title: string;
  snippet: string;
  identity_confidence_score: number;
  match_details: {
    name_found: boolean;
    location_found: boolean;
    url_match_score: number;
  };
}

// POST .../confirmations/{id}
interface ResolveConfirmationRequest {
  action: "confirm" | "reject";
  feedback?: string;  // Optional user feedback
}
```

**Acceptance Criteria:**
- [ ] Auto-confirm when score ≥ 0.8
- [ ] Auto-reject when score < 0.5
- [ ] Pending state for 0.5-0.8 range
- [ ] Confirmation stored with user attribution
- [ ] Bulk confirm/reject endpoint works
- [ ] 10 unit tests + 5 API tests passing

---

### PHASE 3.4: Research Orchestrator

**Goal:** Coordinate crawl → confirmation → ingestion → bio generation.

**File:** `modules/research_orchestrator.py` (NEW)

```python
class ResearchOrchestrator:
    """
    Onboarding-driven research orchestrator.
    
    Flow:
    1. CREATE: User submits links → create research run + crawl
    2. CRAWL: Background job fetches all sources
    3. CONFIRMATION: If ambiguous sources, pause for user confirmation
    4. INGESTION: Ingest confirmed sources via crawl_ingestion_bridge
    5. SYNTHESIS: Trigger bio generation via persona_link_compile hook
    6. READY: Update twin readiness status
    """
    
    async def create_research_run(
        self,
        twin_id: str,
        onboarding_session_id: Optional[str],
        claimed_identity: Dict[str, Any],
        seed_urls: List[str],
    ) -> ResearchRun:
        """Create new research run and enqueue crawl job."""
        
    async def on_crawl_complete(
        self,
        research_run_id: str,
    ) -> None:
        """
        Called when crawl job completes.
        - Create source confirmations
        - If all auto-resolved, proceed to ingestion
        - If pending confirmations, set status awaiting_confirmation
        """
        
    async def on_confirmations_resolved(
        self,
        research_run_id: str,
    ) -> None:
        """
        Called when all sources confirmed/rejected.
        - Ingest confirmed sources
        - Trigger bio generation
        - Update mind score
        """
        
    async def get_run_status(
        self,
        research_run_id: str,
    ) -> ResearchRunStatus:
        """Get full status including pending confirmations."""
```

**State Machine:**

```
planning → crawling → [on_crawl_complete]
    ↓
awaiting_confirmation ──[user confirms all]──→ processing
    ↓                                          ↓
[timeout: 24h]                            ingesting
    ↓                                          ↓
processing (with warnings)               synthesizing
                                              ↓
                                          completed / failed
```

**Acceptance Criteria:**
- [ ] State transitions work correctly
- [ ] Checkpoint/resume at confirmation gate
- [ ] Timeout handling after 24h
- [ ] Event streaming for progress updates
- [ ] 10 unit tests + 5 integration tests passing

---

### PHASE 3.5: Ingestion with Confirmation Gate

**Goal:** Modify ingestion bridge to respect confirmation status.

**File:** `modules/crawl_ingestion_bridge.py` (MODIFY)

**Changes:**
- Add `require_confirmation` parameter (True for onboarding mode)
- Skip ingestion for unconfirmed/rejected pages
- Tombstone rejected pages
- Track ingestion source as "confirmed_crawl" vs "auto_crawl"

```python
async def process_crawl_for_ingestion(
    self,
    crawl_id: str,
    twin_id: Optional[str] = None,
    require_confirmation: bool = True,  # NEW
) -> IngestionStats:
    """
    Process crawl with confirmation gate.
    If require_confirmation=True, only ingest confirmed pages.
    """
```

**Acceptance Criteria:**
- [ ] Only confirmed sources ingested when gate enabled
- [ ] Rejected sources tombstoned
- [ ] Mind score updated post-ingestion
- [ ] 5 unit tests passing

---

## PHASE 4: Bio Generation Integration

### PHASE 4.1: Persona Link Compile Hook

**Goal:** Trigger existing bio generation after confirmed ingestion.

**File:** `modules/research_orchestrator.py` (MODIFY)

```python
async def trigger_bio_generation(
    self,
    twin_id: str,
    research_run_id: str,
    confirmed_sources: List[ConfirmedSource],
):
    """
    Trigger bio generation via existing persona_link_compile flow.
    Additive integration - doesn't replace existing flow.
    """
    from routers.persona_link_compile import (
        ModeCUrlRequest,
        process_mode_c_urls,  # Existing function
    )
    
    # Extract URLs from confirmed sources
    urls = [s.url for s in confirmed_sources if s.confirmation_status == "confirmed"]
    
    # Call existing Mode C processor
    request = ModeCUrlRequest(twin_id=twin_id, urls=urls[:10])  # Limit to 10
    result = await process_mode_c_urls(request, user=...)
    
    # Store reference to research run in bio metadata
    # This links crawl-based sources to generated bios
```

**Acceptance Criteria:**
- [ ] Bio generation triggered after ingestion
- [ ] Uses existing persona_link_compile endpoints
- [ ] Bio variants stored correctly
- [ ] 5 integration tests passing

---

## PHASE 5: Twin-Ready Handoff

### PHASE 5.1: Mind Score Integration Hook

**Goal:** Update mind score after confirmed ingestion.

**File:** `modules/crawl_ingestion_bridge.py` (MODIFY)

```python
async def _update_mind_score(self, twin_id: str):
    """
    Update training metrics/mind score post-ingestion.
    Calls existing training_metrics module.
    """
    from modules.training_metrics import update_twin_training_metrics
    
    metrics = await update_twin_training_metrics(twin_id)
    
    # Log for observability
    logger.info(f"Updated mind score for {twin_id}: {metrics.mind_score}")
    return metrics
```

### PHASE 5.2: Twin Readiness Status

**Goal:** Mark twin as ready when sufficient sources confirmed.

**File:** `modules/twin_readiness.py` (NEW)

```python
class TwinReadinessChecker:
    """
    Determine if twin is ready for chat/profile display.
    
    Criteria:
    - At least 1 confirmed source
    - Mind score ≥ threshold (default: 30)
    - At least 1 bio variant generated
    - No pending confirmations (or timeout passed)
    """
    
    def is_ready(self, twin_id: str) -> ReadinessResult:
        """Check all readiness criteria."""
        
    def get_readiness_status(self, twin_id: str) -> Dict[str, Any]:
        """Get detailed readiness breakdown."""
```

**API Endpoint:**

```python
@router.get("/twins/{twin_id}/research-summary")
async def get_research_summary(twin_id: str):
    """
    Get full research summary for profile page.
    
    Returns:
    {
        "status": "in_progress" | "awaiting_confirmation" | "completed",
        "sources": {
            "confirmed": [...],
            "pending": [...],
            "rejected": [...],
        },
        "bio_variants": [...],
        "mind_score": {
            "score": 65,
            "label": "Developing",
            "words_processed": 15000,
        },
        "is_ready": false,
        "ready_requirements": {
            "has_confirmed_source": true,
            "mind_score_threshold": true,
            "has_bio_variant": false,
            "no_pending_confirmations": false,
        }
    }
    """
```

**Frontend Contract:**

```typescript
interface ResearchSummary {
  status: 'in_progress' | 'awaiting_confirmation' | 'completed';
  sources: {
    confirmed: ConfirmedSource[];
    pending: PendingConfirmation[];
    rejected: RejectedSource[];
  };
  bio_variants: BioVariant[];
  mind_score: {
    score: number;
    label: string;
    words_processed: number;
  };
  is_ready: boolean;
  ready_requirements: {
    [key: string]: boolean;
  };
}
```

**Acceptance Criteria:**
- [ ] Mind score updates after ingestion
- [ ] Readiness criteria configurable
- [ ] Research summary endpoint returns complete status
- [ ] Compatible with StepProfileLanding.tsx
- [ ] 10 integration tests passing

---

## PHASE 6: Final Integration & Regression Testing

### PHASE 6.1: End-to-End Testing

**Test Flows:**
1. **Happy Path:** Submit links → Crawl → Auto-confirm → Ingest → Bio → Ready
2. **Confirmation Gate:** Submit links → Crawl → Pending → User confirms → Ingest → Bio
3. **Rejection Flow:** Submit links → Crawl → Reject some → Ingest confirmed only
4. **Timeout Flow:** Submit links → Crawl → Pending → Timeout → Proceed with confirmed
5. **Recrawl Flow:** Submit same links → Classify unchanged → Skip ingestion → Keep existing bio

### PHASE 6.2: Regression Testing

**Existing Functionality (Must Not Break):**
- [ ] Chat router: All existing chat modes work
- [ ] Standard ingestion: File upload, YouTube, podcast flows
- [ ] Persona link compile: Mode A/B/C still work independently
- [ ] Mind score: Updates correctly for standard ingestion
- [ ] Twin APIs: All existing endpoints function

---

## D) FILE-BY-FILE EXPECTED CHANGES

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `modules/firecrawl_client.py` | ~300 | Production Firecrawl client with retry, circuit breaker, error mapping |
| `modules/identity_confidence_scorer.py` | ~200 | Identity matching algorithm |
| `modules/crawl_job_processor.py` | ~400 | Background job processor for crawl execution |
| `modules/source_confirmation.py` | ~250 | Confirmation state management |
| `modules/research_orchestrator.py` | ~350 | Research run lifecycle + checkpointing |
| `modules/twin_readiness.py` | ~150 | Readiness criteria checker |
| `tests/test_firecrawl_client.py` | ~150 | Unit tests for Firecrawl client |
| `tests/test_identity_scorer.py` | ~100 | Unit tests for identity scoring |
| `tests/test_source_confirmation.py` | ~120 | Unit tests for confirmation system |
| `tests/test_research_orchestrator.py` | ~150 | Integration tests for orchestration |
| `migrations/migration_phase3_research_tables.sql` | ~100 | Database migrations |

### Modified Files

| File | Changes | Purpose |
|------|---------|---------|
| `modules/deep_research_config.py` | +50 lines | Add FirecrawlConfig class |
| `modules/web_crawler.py` | +30/-20 lines | Refactor to use new firecrawl_client |
| `modules/crawl_ingestion_bridge.py` | +40 lines | Add confirmation gate parameter |
| `modules/crawl_repository.py` | +20 lines | Add research run association methods |
| `routers/crawl.py` | +150 lines | Add confirmation endpoints |
| `main.py` | +10 lines | Register new job processor |

### Files Preserved (No Changes)

| File | Reason |
|------|--------|
| `routers/chat.py` | No crawl dependencies; additive only |
| `routers/ingestion.py` | Existing pipeline preserved |
| `routers/twins.py` | Mind score integration via hooks |
| `modules/training_metrics.py` | Called via existing API |
| `routers/persona_link_compile.py` | Triggered via existing endpoints |
| `modules/retrieval.py` | Tombstone filter already in place |
| `modules/pinecone_adapter.py` | Versioned metadata already in place |

---

## E) TEST PLAN

### Unit Tests (New)

| Module | Tests | Coverage |
|--------|-------|----------|
| `firecrawl_client.py` | 15 | Retry logic, error mapping, circuit breaker |
| `identity_confidence_scorer.py` | 15 | Name matching, location matching, URL matching |
| `source_confirmation.py` | 12 | State transitions, bulk operations |
| `research_orchestrator.py` | 15 | State machine, checkpointing |
| `crawl_job_processor.py` | 15 | Source strategies, Firecrawl integration |
| **Total New** | **72** | |

### Integration Tests (New)

| Flow | Tests |
|------|-------|
| Happy path E2E | 3 |
| Confirmation gate | 3 |
| Rejection flow | 2 |
| Timeout handling | 2 |
| Recrawl idempotency | 3 |
| Mind score update | 2 |
| Bio generation trigger | 2 |
| **Total Integration** | **17** | |

### Regression Tests (Existing)

| Suite | Tests | Must Pass |
|-------|-------|-----------|
| Phase 1A tests | 175 | ✅ |
| Phase 1B tests | 89 | ✅ |
| Phase 2 tests | 40 | ✅ |
| Chat router tests | All | ✅ |
| Ingestion tests | All | ✅ |
| Persona link compile | All | ✅ |

### Test Execution Order

1. **Phase 3.0:** Unit tests for Firecrawl client (15)
2. **Phase 3.1:** Unit tests for identity scorer (15)
3. **Phase 3.2:** Unit + integration tests for job processor (20)
4. **Phase 3.3:** Unit + API tests for confirmation (20)
5. **Phase 3.4:** Integration tests for orchestrator (15)
6. **Phase 4-5:** End-to-end tests (17)
7. **Phase 6:** Full regression suite (304+ existing)

**Total New Tests:** 89 unit/integration  
**Total Tests After Phase 6:** 393+

---

## F) RISK LIST + ROLLBACK STRATEGY

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Firecrawl API changes | Medium | High | Wrapper module isolates changes; pin version in requirements |
| Firecrawl rate limiting | High | Medium | Implement circuit breaker; graceful degradation to manual path |
| Identity scoring false positives | Medium | High | Configurable thresholds; user override always available |
| Confirmation UX friction | Medium | Medium | Auto-confirm high confidence; bulk actions; 24h timeout |
| Database migration failure | Low | High | Test migrations in staging; backward-compatible schema changes |
| Breaking existing flows | Low | Critical | Feature flag `DEEP_RESEARCH_ENABLED`; additive-only changes |

### Rollback Strategy

**Per-Phase Rollback:**

| Phase | Rollback Action |
|-------|-----------------|
| 3.0 | Revert imports; drop new tables; disable Firecrawl |
| 3.1 | Disable identity scoring (use default 1.0) |
| 3.2 | Stop crawl job processor; mark jobs as failed |
| 3.3 | Auto-confirm all pending; disable confirmation UI |
| 3.4 | Disable orchestrator; use simple crawl → ingest |
| 4-5 | Skip bio generation; use existing manual flow |

**Emergency Kill Switch:**
```python
# In deep_research_config.py
DEEP_RESEARCH_GLOBAL_DISABLE = os.getenv("DEEP_RESEARCH_GLOBAL_DISABLE", "false")
```

**Database Rollback:**
- All migrations are additive (new tables, new nullable columns)
- Rollback = remove code references; tables can remain empty
- No destructive migrations (no DROP COLUMN, no ALTER TYPE)

**Feature Flag Strategy:**
```python
# Each phase has its own flag
DEEP_RESEARCH_PHASE_3_0_ENABLED = os.getenv("DR_PHASE_3_0", "false")
DEEP_RESEARCH_PHASE_3_3_ENABLED = os.getenv("DR_PHASE_3_3", "false")  # Confirmation gate
```

---

## G) STOP

**This is a planning document only. No implementation has been performed.**

**Next Steps (Require Explicit Go-Ahead):**
1. Review and approve Phase 3.0-3.5 breakdown
2. Confirm Firecrawl API key provisioning for dev/staging/prod
3. Assign Phase 3.0 implementation (prerequisite for all subsequent phases)
4. Schedule Phase 3.0 code review before proceeding to 3.1

**Ready to Proceed:** Phase 3.0 can begin immediately upon approval.

**Estimated Timeline:**
- Phase 3.0: 2 days
- Phase 3.1-3.3: 4 days (parallel where possible)
- Phase 3.4-3.5: 3 days
- Phase 4-5: 2 days
- Phase 6 (testing): 3 days
- **Total: 14 days**

---

**END OF PLAN**
