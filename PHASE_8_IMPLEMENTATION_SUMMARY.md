# Phase 8: Claims Enrichment MVP - Implementation Summary

## Overview
Phase 8 adds **Claims Enrichment** to the Deep Research pipeline, extracting atomic claims from confirmed/ingested sources and verifying them locally (Phase 8 scope: local verification only).

## ✅ Completed Components

### 1. Database Layer
**File:** `backend/database/migrations/migration_phase_8_claims.sql`

- `research_claims` table: Stores extracted claims
- `research_claim_evidence` table: Stores supporting evidence quotes
- Added `claims_checkpoint` to `research_runs`
- Indexes for performance

### 2. Core Modules

#### Claim Extractor
**File:** `backend/modules/research_claim_extractor.py`

```python
ResearchClaimExtractor.extract_from_sources(sources, twin_id) -> List[ResearchClaim]
extract_claims_from_research_sources(sources, twin_id, research_run_id) -> Dict
```

- Extracts atomic claims from ingested content
- Classifies claims: preference, belief, heuristic, value, experience, boundary, uncertain
- Supports deterministic test mode via injectable LLM function

#### Claim Verifier
**File:** `backend/modules/research_claim_verifier.py`

```python
ClaimVerifier.verify_claim(claim, sources) -> VerificationResult
verify_research_claims(claims, sources) -> Dict
```

- Local verification against ingested sources only (no web search)
- Uses TF-IDF similarity for evidence matching
- Statuses: supported, insufficient_evidence, conflicting, needs_review

#### Claim Service
**File:** `backend/modules/research_claim_service.py`

```python
ResearchClaimService.enrich_research_run(run_id, twin_id) -> EnrichmentSummary
```

- Orchestrates extraction → verification → persistence
- Idempotent: safe to retry without duplication
- Updates checkpoint data in research_runs

### 3. API Router
**File:** `backend/routers/research_claims.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/twins/{twin_id}/research/{research_run_id}/continue-claims` | POST | Trigger claims enrichment (idempotent) |
| `/twins/{twin_id}/research/{research_run_id}/claims-status` | GET | Get enrichment status |
| `/twins/{twin_id}/research/{research_run_id}/claims` | GET | List claims with filtering |
| `/twins/{twin_id}/research/{research_run_id}/claims/{claim_id}/resolve` | POST | Manually resolve a claim |

### 4. Integration Points

#### Main App
**File:** `backend/main.py`

```python
# Claims router included when Deep Research is enabled
if DEEP_RESEARCH_ENABLED:
    app.include_router(research_claims.router)
    print("[INFO] Deep Research claims routes enabled")
```

#### Crawl Router
**File:** `backend/routers/crawl.py`

Added `continue-claims` endpoint that:
1. Checks `DR_PHASE_8_CLAIMS_DISABLED` feature flag
2. Validates run is in `COMPLETED` or `CLAIMS_ENRICHMENT` state
3. Calls `ClaimEnrichmentService.enrich_research_run()`
4. Returns claims summary

#### State Machine
**File:** `backend/modules/research_orchestrator.py`

Extended `ResearchRunStatus`:
```python
class ResearchRunStatus(str, Enum):
    # ... phases 1-7 ...
    COMPLETED = "completed"          # Phase 5 terminal → now non-terminal
    CLAIMS_ENRICHMENT = "claims_enrichment"  # Phase 8
    CLAIMS_COMPLETED = "claims_completed"    # Phase 8 terminal
```

Valid transitions:
- `COMPLETED` → `CLAIMS_ENRICHMENT` (optional)
- `CLAIMS_ENRICHMENT` → `CLAIMS_COMPLETED`
- `CLAIMS_ENRICHMENT` → `FAILED`

### 5. Tests
**File:** `backend/tests/test_research_claims.py`

22 tests covering:
- Claim extraction (empty, short, mock LLM, multiple sources)
- Claim verification (strong support, no support, weak support)
- Service layer (initialization, status checking)
- API contracts (enum values match expectations)
- Feature flags (DR_PHASE_8_CLAIMS_DISABLED)
- Full enrichment pipeline integration
- Idempotency

**Test Results:** 22/22 passing

```
tests/test_research_claims.py::TestResearchClaim::test_claim_creation PASSED
tests/test_research_claims.py::TestResearchClaimExtractor::test_extract_from_source_mock_llm PASSED
tests/test_research_claims.py::TestClaimVerifier::test_verify_claim_with_strong_support PASSED
tests/test_research_claims.py::test_full_enrichment_pipeline PASSED
...
========================= 22 passed in 1.73s =========================
```

## 🔧 Feature Flags

### Master Flag
```bash
DEEP_RESEARCH_ENABLED=true  # Required for all research features
```

### Phase 8 Specific
```bash
DR_PHASE_8_CLAIMS_DISABLED=false  # Set to 'true' to disable only Phase 8
                                  # Phases 1-7 continue working
```

Flag hierarchy:
1. `DEEP_RESEARCH_ENABLED=false` → Disables all research (Phases 1-8)
2. `DR_PHASE_8_CLAIMS_DISABLED=true` → Disables only Phase 8

## 📊 Verification Statuses

| Status | Description |
|--------|-------------|
| `pending` | Newly extracted, awaiting verification |
| `supported` | Strong evidence found (2+ sources or high relevance) |
| `insufficient_evidence` | No or weak evidence found |
| `conflicting` | Evidence contradicts claim |
| `needs_review` | Ambiguous - requires manual review |

## 🔁 Idempotency

All enrichment operations are idempotent:
- Safe to retry `continue-claims` endpoint
- Duplicate claims prevented via content hashing
- Checkpoint tracking prevents re-processing

## 🔄 API Usage

### Trigger Claims Enrichment
```bash
POST /twins/{twin_id}/research/{research_run_id}/continue-claims

Response:
{
  "research_run_id": "run-123",
  "status": "claims_enrichment",
  "previous_status": "completed",
  "claims": {
    "total_extracted": 15,
    "by_status": {
      "supported": 8,
      "insufficient_evidence": 4,
      "needs_review": 3
    }
  },
  "message": "Claims enrichment completed"
}
```

### List Claims
```bash
GET /twins/{twin_id}/research/{research_run_id}/claims?status=supported&limit=10

Response:
{
  "items": [
    {
      "id": "claim-456",
      "claim_text": "I prefer Python over JavaScript",
      "claim_type": "preference",
      "verification_status": "supported",
      "confidence": 0.92,
      "evidence_quotes": [...]
    }
  ],
  "total": 15,
  "limit": 10,
  "offset": 0,
  "has_more": true
}
```

## 🎯 Design Decisions

1. **Local Verification Only (Phase 8)**: No web search for verification - uses only ingested sources
2. **Separate from Persona Claims**: `research_claims` table is distinct from `persona_claims` (which are for Link/Compile)
3. **Optional Phase**: Research runs can complete without claims enrichment (`COMPLETED` is still a valid terminal state)
4. **Additive Only**: Phase 8 doesn't modify Phases 1-7 transitions, only extends from `COMPLETED`
5. **Deterministic Testing**: All LLM calls are mockable via dependency injection

## 📁 Files Created/Modified

### New Files
- `backend/modules/research_claim_extractor.py`
- `backend/modules/research_claim_verifier.py`
- `backend/modules/research_claim_service.py`
- `backend/routers/research_claims.py`
- `backend/tests/test_research_claims.py`
- `backend/database/migrations/migration_phase_8_claims.sql`

### Modified Files
- `backend/main.py` - Added claims router registration
- `backend/routers/crawl.py` - Added `continue-claims` endpoint
- `backend/modules/research_orchestrator.py` - Extended state machine
- `backend/modules/deep_research_config.py` - Added `DR_PHASE_8_CLAIMS_DISABLED` flag

## ✅ Verification Checklist

- [x] Database migration created with IF NOT EXISTS safety
- [x] All 22 Phase 8 tests passing
- [x] App starts successfully with new routes
- [x] Feature flags working correctly
- [x] API endpoints return correct response models
- [x] State machine transitions validated
- [x] Idempotency verified
- [x] No breaking changes to Phases 1-7
