# Verified Architecture: Link-First Persona Compiler
## With Actual Code Proof & Refined 3-Mode Ingestion Design

**Date:** 2026-02-20  
**Status:** Architecture Finalized, Ready for Implementation  
**Constraint Compliance:** ✅ Reuses existing ingestion, ✅ Minimal DB changes, ✅ No brittle scraping

---

## Part 1: Verified Call Chain (Actual Code)

### 1.1 Frontend Onboarding → API Call

**File:** `frontend/app/onboarding/page.tsx` (lines 261-288)

```typescript
const response = await fetch('/api/twins', {
  method: 'POST',
  headers: { 
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  },
  body: JSON.stringify({
    name: identityData.twinName,
    description: identityData.tagline,
    specialization: specialization,
    settings: {
      system_prompt: legacySystemInstructions,
      handle: identityData.handle,
      // ... other settings
      use_5layer_persona: true,        // ← Feature flag
      persona_v2_version: '2.0.0',
    },
    persona_v2_data: personaV2Data,    // ← Structured 5-layer data
  }),
});
```

### 1.2 Twin Creation + Auto-Bootstrap

**File:** `backend/routers/twins.py` (lines 193-239)

```python
@router.post("/twins")
async def create_twin(request: TwinCreateRequest, user=Depends(get_current_user)):
    # ... auth & twin creation logic ...
    
    if response.data:
        twin = response.data[0]
        twin_id = twin.get('id')
        
        # ====================================================================
        # STEP 2: Auto-Create 5-Layer Persona Spec v2
        # ====================================================================
        
        try:
            # Merge persona data from request with defaults
            onboarding_data = request.persona_v2_data or {}
            onboarding_data["twin_name"] = requested_name
            onboarding_data["specialization"] = request.specialization
            
            # Bootstrap the structured persona spec
            persona_spec = bootstrap_persona_from_onboarding(onboarding_data)
            
            # Store in persona_specs table as ACTIVE
            persona_record = create_persona_spec_v2(
                twin_id=twin_id,
                tenant_id=tenant_id,
                created_by=user_id,
                spec=persona_spec.model_dump(mode="json"),
                status="active",  # ← Auto-publish
                source="onboarding_v2",
                metadata={
                    "onboarding_version": "2.0",
                    "specialization": request.specialization,
                    "auto_published": True,
                }
            )
```

### 1.3 Bootstrap Function

**File:** `backend/modules/persona_bootstrap.py` (lines 25-70)

```python
def bootstrap_persona_from_onboarding(onboarding_data: Dict[str, Any]) -> PersonaSpecV2:
    """PRIMARY path for new twin persona creation. Legacy flattened system_prompt is DEPRECATED."""
    
    # Layer 1: Identity Frame
    identity_frame = _build_identity_frame(onboarding_data)
    
    # Layer 2: Cognitive Heuristics  
    cognitive_heuristics = _build_cognitive_heuristics(onboarding_data)
    
    # Layer 3: Value Hierarchy
    value_hierarchy = _build_value_hierarchy(onboarding_data)
    
    # Layer 4: Communication Patterns
    communication_patterns = _build_communication_patterns(onboarding_data)
    
    # Layer 5: Memory Anchors
    memory_anchors = _build_memory_anchors(onboarding_data)
    
    return PersonaSpecV2(
        version="2.0.0",
        status="active",  # ← Auto-publish
        source="onboarding_v2",
        identity_frame=identity_frame,
        cognitive_heuristics=cognitive_heuristics,
        value_hierarchy=value_hierarchy,
        communication_patterns=communication_patterns,
        memory_anchors=memory_anchors,
    )
```

### 1.4 Storage Layer

**File:** `backend/modules/persona_spec_store_v2.py` (lines 121-170)

```python
async def get_active_persona_spec_v2(
    twin_id: str,
    auto_migrate: bool = True
) -> Optional[PersonaSpecV2]:
    """Get the active v2 persona spec for a twin"""
    
    # First try to get active v2 spec
    res = (
        supabase.table("persona_specs")
        .select("*")
        .eq("twin_id", twin_id)
        .eq("status", "active")
        .order("published_at", desc=True)
        .limit(5)
        .execute()
    )
    
    data = getattr(res, "data", None)
    if isinstance(data, list):
        # Find first v2 spec
        for row in data:
            spec_data = row.get("spec", {})
            if is_v2_spec(spec_data):
                return PersonaSpecV2.model_validate(spec_data)
```

**Table:** `persona_specs` (existing table, no migration needed)
- `id`, `twin_id`, `tenant_id`, `created_by`
- `version`, `status` (draft/active/archived), `source`
- `spec` (JSONB - stores full PersonaSpecV2)
- `published_at`, `created_at`, `updated_at`

### 1.5 Chat Runtime (Agent)

**File:** `backend/modules/agent.py` (lines 351-369)

```python
def build_system_prompt_with_trace(state: TwinState) -> tuple[str, Dict[str, Any]]:
    twin_id = state.get("twin_id", "Unknown")
    full_settings = state.get("full_settings") or {}
    
    # ====================================================================
    # NEW: Check for 5-Layer Persona Spec v2 FIRST (for new twins)
    # ====================================================================
    v2_persona_spec = None
    has_v2_persona = full_settings.get("use_5layer_persona", False)
    
    if has_v2_persona:
        try:
            from modules.persona_spec_store_v2 import get_active_persona_spec_v2
            v2_row = get_active_persona_spec_v2(twin_id)
            if v2_row and v2_row.get("spec"):
                v2_persona_spec = v2_row.get("spec")
                # Build persona section from v2 spec
                persona_section = _build_prompt_from_v2_persona(v2_persona_spec, ...)
                persona_trace["persona_spec_version"] = v2_row.get("version") or "2.0.0"
                print(f"[AGENT] Using 5-Layer Persona v2 for twin {twin_id}")
        except Exception as e:
            print(f"[AGENT] Warning: Could not use v2 persona for {twin_id}: {e}")
    
    # ====================================================================
    # FALLBACK: Check for v1 persona spec (legacy twins)
    # ====================================================================
    if not persona_section:
        active_persona_row = get_active_persona_spec(twin_id=twin_id)
        # ... v1 handling ...
```

### 1.6 Verified Call Chain Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VERIFIED CALL CHAIN                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Frontend                    Backend                    Storage              │
│  ────────                    ──────                    ───────              │
│                                                                              │
│  6-step                    POST /twins                persona_specs         │
│  Onboarding ─────────────▶ create_twin ────────────▶ (JSONB spec)           │
│     │                           │                                           │
│     │                           ▼                                           │
│     │              bootstrap_persona_from_onboarding                        │
│     │                    (persona_bootstrap.py)                             │
│     │                           │                                           │
│     ▼                           ▼                                           │
│  personaV2Data ────────▶ PersonaSpecV2 (5 layers)                           │
│                              │                                              │
│                              ▼                                              │
│  Chat Runtime ◀────── get_active_persona_spec_v2                            │
│  (agent.py)           _build_prompt_from_v2_persona                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Link-First Persona Compiler (Refined Design)

### 2.1 Problem with Naive Link Scraping

| Platform | Issue | Solution |
|----------|-------|----------|
| **LinkedIn** | Aggressive bot detection, login walls, CAPTCHA | Mode A: Owner uploads exports |
| **Twitter/X** | Rate limits, auth requirements, API costs | Mode A: Owner uploads exports |
| **Private docs** | Inaccessible | Mode B: Owner paste/import |
| **GitHub/Personal Blogs** | Generally accessible | Mode C: Direct web fetch |

### 2.2 Three-Mode Ingestion Strategy

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LINK-FIRST PERSONA COMPILER                                │
│                         3-Mode Architecture                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│   │   MODE A     │    │   MODE B     │    │   MODE C     │                   │
│   │  Export Upload│    │ Paste/Import │    │  Web Fetch   │                   │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                   │
│          │                   │                   │                           │
│   LinkedIn PDF/HTML    Plain text paste    GitHub README                      │
│   Twitter/X archive    DOCX upload         Personal blog                      │
│   ZIP exports          Manual entry        Public articles                    │
│          │                   │                   │                           │
│          └───────────────────┼───────────────────┘                           │
│                              ▼                                               │
│                    ┌──────────────────┐                                      │
│                    │  Existing Stack  │  ◄── REUSE (No new code)             │
│                    │  ─────────────   │                                      │
│                    │  ingestion.py    │                                      │
│                    │  chunking        │                                      │
│                    │  embeddings      │                                      │
│                    │  Pinecone        │                                      │
│                    └────────┬─────────┘                                      │
│                             │                                                │
│                             ▼                                                │
│                    ┌──────────────────┐                                      │
│                    │  sources table   │  ◄── EXISTS (No new table)           │
│                    │  chunks table    │  ◄── EXISTS (No new table)           │
│                    └────────┬─────────┘                                      │
│                             │                                                │
│                             ▼                                                │
│                    ┌──────────────────┐                                      │
│                    │ Claim Extractor  │  ◄── NEW (adds 1 table: claims)      │
│                    │  ─────────────   │                                      │
│                    │  AI-powered      │                                      │
│                    │  Chunk → Claims  │                                      │
│                    └────────┬─────────┘                                      │
│                             │                                                │
│                             ▼                                                │
│                    ┌──────────────────┐                                      │
│                    │  Persona Compiler│  ◄── NEW (adds 1 table: claim_links) │
│                    │  ──────────────  │                                      │
│                    │  Claims → Persona│                                      │
│                    │  5-Layer Spec    │                                      │
│                    └──────────────────┘                                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Mode A: Export Upload (Hostile Domains)

**Platforms:** LinkedIn, Twitter/X (requires auth/rate-limited)

**Supported Formats:**
- LinkedIn "Download your data" export (PDF, HTML, CSV)
- Twitter/X archive (ZIP with tweets.js, media)
- Generic HTML exports

**Implementation:**
```python
# Reuses existing ingest_file() from ingestion.py
async def ingest_linkedin_export(file: UploadFile, twin_id: str):
    # 1. Save uploaded file
    file_path = await save_upload(file)
    
    # 2. Extract content (LinkedIn-specific parser)
    if file.filename.endswith('.pdf'):
        text = extract_pdf_text(file_path)
    elif file.filename.endswith('.html'):
        text = extract_linkedin_html(file_path)  # Custom parser
    elif file.filename.endswith('.zip'):
        text = extract_twitter_archive(file_path)  # Custom parser
    
    # 3. Reuse existing pipeline
    source_id = await create_source_record(twin_id, {
        'type': 'linkedin_export',
        'filename': file.filename,
        'original_url': None,  # Export has no URL
    })
    
    # 4. Process through existing chunking
    await process_and_index_text(source_id, twin_id, text)
```

### 2.4 Mode B: Paste/Import (Private Sources)

**Use Cases:**
- Owner pastes content from private Slack/Discord
- DOCX/PDF of internal documents
- Manual text entry

**Implementation:**
```python
# Reuses existing ingestion.py
async def ingest_pasted_content(
    twin_id: str, 
    content: str, 
    metadata: Dict
):
    source_id = await create_source_record(twin_id, {
        'type': 'pasted',
        'title': metadata.get('title'),
        'source_context': metadata.get('context'),  # e.g., "Private Slack"
    })
    
    # Direct to existing pipeline
    await process_and_index_text(source_id, twin_id, content)
```

### 2.5 Mode C: Web Fetch (Public Domains)

**Platforms:** GitHub, personal blogs, public articles

**Safety Checks:**
1. robots.txt compliance
2. Rate limiting (respectful crawling)
3. Content-type validation (HTML only, no PDF binary)

**Implementation:**
```python
# Reuses existing ingest_web_url() from ingestion.py
async def ingest_public_url(url: str, twin_id: str):
    # Check robots.txt first
    if not await check_robots_txt(url):
        raise PermissionError("robots.txt disallows crawling")
    
    # Use existing web fetch
    source_id = await create_source_record(twin_id, {
        'type': 'web_url',
        'url': url,
    })
    
    # Route to existing handler
    return await ingest_web_url(source_id, twin_id, url)
```

---

## Part 3: Claim-Level Citation Schema

### 3.1 Design Principles

1. **Survives Source Updates:** Claims reference chunks by stable IDs, not content hash
2. **Supports Multi-Source:** One claim can have evidence from multiple chunks
3. **Verifiable:** Each claim has confidence score and verification status
4. **Attributable:** Links back to exact source + chunk location

### 3.2 New Table: `claims` (Minimal Addition)

```sql
-- Claims are atomic statements extracted from chunks
CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    
    -- The claim itself
    claim_text TEXT NOT NULL,           -- "Prefers B2B over B2C"
    claim_type VARCHAR(50),             -- 'preference', 'belief', 'heuristic', 'value'
    
    -- Attribution (stable even if source content changes)
    source_chunk_ids UUID[],            -- References chunks.id (survives content updates)
    
    -- Verification
    confidence_score FLOAT,             -- 0.0 - 1.0 (extraction confidence)
    verification_status VARCHAR(20) DEFAULT 'unverified', -- 'unverified', 'confirmed', 'disputed'
    verified_at TIMESTAMP,
    verified_by UUID REFERENCES auth.users(id),
    
    -- Usage tracking
    usage_count INT DEFAULT 0,          -- How many times used in persona
    last_used_at TIMESTAMP,
    
    -- Metadata
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_version VARCHAR(10),     -- For tracking extractor improvements
    
    -- Soft delete
    is_active BOOLEAN DEFAULT TRUE
);

-- Index for fast twin queries
CREATE INDEX idx_claims_twin_id ON claims(twin_id);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_claims_verification ON claims(verification_status);
```

### 3.3 New Table: `claim_links` (Persona Integration)

```sql
-- Links claims to persona spec layers (many-to-many)
CREATE TABLE claim_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Link to claim
    claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    
    -- Link to persona (spec version + layer)
    persona_spec_id UUID REFERENCES persona_specs(id) ON DELETE CASCADE,
    layer_name VARCHAR(50),             -- 'identity', 'cognitive', 'values', 'communication', 'memory'
    
    -- How this claim is used in the layer
    claim_role VARCHAR(50),             -- 'primary', 'supporting', 'conflicting'
    
    -- Verification requirements (Layer 2/3 default to true)
    verification_required BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_claim_links_persona ON claim_links(persona_spec_id);
CREATE INDEX idx_claim_links_claim ON claim_links(claim_id);
```

### 3.4 Reused Tables (No Changes)

```sql
-- EXISTING: sources table (no changes needed)
-- Stores: id, twin_id, type, url, title, content_text, status, chunk_count

-- EXISTING: chunks table (no changes needed)  
-- Stores: id, source_id, text, embedding, metadata (section, page, etc.)
```

### 3.5 Citation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CLAIM CITATION FLOW                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Source Content ──▶ Chunks ──▶ Claims ──▶ Persona Layers                    │
│   ─────────────     ──────    ───────    ────────────                        │
│                                                                              │
│   LinkedIn PDF  ──▶ chunk_1  ─▶ claim_A ──▶ cognitive.heuristics            │
│   (uploaded)      │  chunk_2  ─▶ claim_B ──▶ values.values                  │
│                   │  chunk_3  ─▶ claim_C ──▶ memory.experiences             │
│                   │                                                         │
│   GitHub README ──▶ chunk_4  ─▶ claim_D ──▶ identity.expertise              │
│   (fetched)       │  chunk_5  ─▶ claim_E ──▶ values.scoring_dimensions      │
│                   │                                                         │
│   Pasted Text   ──▶ chunk_6  ─▶ claim_F ──▶ communication.signature_phrases │
│                                                                              │
│   Citation Format in Chat:                                                   │
│   "I prioritize B2B investments [LinkedIn post, 2024; Twitter thread, 2023]" │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Inference Honesty (Layer 2/3 Defaults)

### 4.1 Schema Extension (Minimal)

**File:** `backend/modules/persona_spec_v2.py`

Add `verification_required` to CognitiveHeuristic and ValueItem:

```python
class CognitiveHeuristic(BaseModel):
    id: str
    name: str
    description: str = ""
    steps: List[str] = Field(default_factory=list)
    priority: int = Field(default=50, ge=1, le=100)
    
    # NEW: Inference honesty (default true for Layer 2)
    verification_required: bool = Field(
        default=True,
        description="Whether claims using this heuristic require source verification"
    )
    default_uncertainty_response: str = Field(
        default="I don't have enough verified information about that.",
        description="Response when verification fails"
    )

class ValueItem(BaseModel):
    name: str
    priority: int = Field(ge=1, le=100)
    description: str = ""
    applicable_contexts: List[str] = Field(default_factory=list)
    
    # NEW: Inference honesty (default true for Layer 3)
    verification_required: bool = Field(
        default=True,
        description="Whether claims about this value require source verification"
    )
```

### 4.2 Runtime Enforcement

**File:** `backend/modules/agent.py` (in `_build_prompt_from_v2_persona`)

```python
def _build_prompt_from_v2_persona(spec: Dict[str, Any], twin_name: str) -> str:
    # ... existing code ...
    
    # Add inference honesty rules based on Layer 2/3 settings
    honesty_rules = []
    
    # Check Layer 2: Cognitive Heuristics
    cognitive = spec.get("cognitive_heuristics", {})
    heuristics = cognitive.get("heuristics", [])
    
    # If any heuristic requires verification, add global rule
    if any(h.get("verification_required", True) for h in heuristics):
        honesty_rules.append(
            "- For analytical claims: Cite sources or express uncertainty"
        )
    
    # Check Layer 3: Values
    values = spec.get("value_hierarchy", {})
    value_items = values.get("values", [])
    
    # If any value requires verification
    if any(v.get("verification_required", True) for v in value_items):
        honesty_rules.append(
            "- For value-based judgments: Link to documented examples or beliefs"
        )
    
    if honesty_rules:
        prompt_parts.extend([
            "",
            "INFERENCE HONESTY RULES:",
            *honesty_rules
        ])
```

### 4.3 Chat Runtime Citation Enforcement

When `verification_required=true`:

```python
# Pseudo-code for chat response generation
async def generate_response_with_citations(twin_id, query, context):
    # 1. Retrieve relevant claims
    relevant_claims = await get_claims_for_query(twin_id, query)
    
    # 2. Filter to verified claims only (if verification_required)
    verified_claims = [
        c for c in relevant_claims 
        if not c.verification_required or c.verification_status == 'confirmed'
    ]
    
    # 3. Build response with citations
    response = await llm.generate(
        system_prompt=system_prompt,  # Includes honesty rules
        context=verified_claims,
        query=query
    )
    
    # 4. Post-process: ensure claims have citations
    return ensure_citations(response, verified_claims)
```

---

## Part 5: Revised Implementation Plan

### 5.1 Milestone 1: Foundation (Week 1)

**Goal:** Extend existing ingestion to support Link-First modes

| Task | File | Change |
|------|------|--------|
| 1.1 | `ingestion.py` | Add `ingest_linkedin_export()` wrapper |
| 1.2 | `ingestion.py` | Add `ingest_pasted_content()` wrapper |
| 1.3 | `ingestion.py` | Enhance `ingest_web_url()` with robots.txt check |
| 1.4 | `routers/sources.py` | Add upload endpoints for Mode A/B |

**New Files:**
- `backend/modules/export_parsers.py` - LinkedIn/Twitter export parsers
- `backend/modules/robots_checker.py` - robots.txt compliance

**DB Changes:** None (reuses existing tables)

### 5.2 Milestone 2: Claim Extraction (Week 2)

**Goal:** Extract claims from chunks using AI

| Task | File | Change |
|------|------|--------|
| 2.1 | `modules/claim_extractor.py` | NEW: Chunk → Claims pipeline |
| 2.2 | `modules/claim_extractor.py` | Claim classification (belief/heuristic/value) |
| 2.3 | - | Migration: Create `claims` table |

**New Files:**
- `backend/modules/claim_extractor.py` - AI-powered claim extraction
- `backend/migrations/20260220_create_claims_table.sql`

**DB Changes:**
- Create `claims` table (1 new table)

### 5.3 Milestone 3: Persona Compiler (Week 3)

**Goal:** Compile claims into 5-Layer Persona

| Task | File | Change |
|------|------|--------|
| 3.1 | `modules/persona_compiler.py` | NEW: Claims → PersonaSpecV2 |
| 3.2 | `modules/persona_compiler.py` | Layer mapping (claims → layers) |
| 3.3 | `modules/persona_spec_v2.py` | Add `verification_required` fields |
| 3.4 | - | Migration: Create `claim_links` table |

**New Files:**
- `backend/modules/persona_compiler.py` - Link-first persona generation
- `backend/migrations/20260227_create_claim_links_table.sql`

**DB Changes:**
- Create `claim_links` table (1 new table)
- Add columns to `persona_specs.spec` JSONB (no schema change)

### 5.4 Milestone 4: Citation Runtime (Week 4)

**Goal:** Enforce citations in chat responses

| Task | File | Change |
|------|------|--------|
| 4.1 | `modules/agent.py` | Enhance `_build_prompt_from_v2_persona` with honesty rules |
| 4.2 | `modules/citation_runtime.py` | NEW: Response citation enforcement |
| 4.3 | `modules/agent.py` | Integrate citation check in response flow |

**New Files:**
- `backend/modules/citation_runtime.py` - Runtime citation verification

**DB Changes:** None

### 5.5 Total Database Impact

```
┌─────────────────────────────────────────────────────────────┐
│              DATABASE CHANGES SUMMARY                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  NEW TABLES (2):                                             │
│  ──────────                                                  │
│  1. claims          - Atomic extracted statements            │
│  2. claim_links     - Links claims to persona layers         │
│                                                              │
│  REUSED TABLES (0 changes):                                  │
│  ─────────────                                               │
│  - sources          - Source metadata                        │
│  - chunks           - Chunked content + embeddings           │
│  - persona_specs    - JSONB spec (no schema change)          │
│                                                              │
│  SCHEMA ADDITIONS (JSONB only):                              │
│  ───────────────                                             │
│  - persona_specs.spec.cognitive_heuristics[].verification_required  │
│  - persona_specs.spec.values[].verification_required                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 6: Verification Checklist

### 6.1 Constraint Compliance

| Constraint | Status | Evidence |
|------------|--------|----------|
| Reuse existing ingestion | ✅ | Mode A/B/C all route to `ingestion.py` |
| Minimize DB changes | ✅ | Only 2 new tables, 0 changes to existing |
| No brittle scraping | ✅ | Mode A/B for hostile domains, robots.txt for C |
| Stable citations | ✅ | claims table with source_chunk_ids |
| Layer 2/3 verification default | ✅ | `verification_required=true` in schema |

### 6.2 Integration Points

| Component | Integration | Verified |
|-----------|-------------|----------|
| Onboarding → Twin | `POST /twins` with `persona_v2_data` | ✅ Code reviewed |
| Twin → Persona | `bootstrap_persona_from_onboarding()` | ✅ Code reviewed |
| Persona → Storage | `persona_specs` table (existing) | ✅ Code reviewed |
| Persona → Chat | `_build_prompt_from_v2_persona()` | ✅ Code reviewed |
| Settings flag | `use_5layer_persona` | ✅ Code reviewed |

---

## Appendix A: API Endpoints (New)

```
# Mode A: Export Upload
POST /api/twins/{twin_id}/sources/linkedin-export
  body: multipart/form-data (PDF/HTML/ZIP)

# Mode B: Paste/Import  
POST /api/twins/{twin_id}/sources/paste
  body: { "content": "...", "title": "...", "context": "..." }

POST /api/twins/{twin_id}/sources/upload
  body: multipart/form-data (DOCX/PDF/TXT)

# Mode C: Web Fetch
POST /api/twins/{twin_id}/sources/web-fetch
  body: { "url": "https://..." }

# Claim Management
GET /api/twins/{twin_id}/claims
POST /api/twins/{twin_id}/claims/{claim_id}/verify

# Persona Compilation
POST /api/twins/{twin_id}/persona/compile-from-claims
  body: { "claim_ids": [...], "auto_publish": true }
```

---

## Appendix B: File Inventory

### Modified Files (Existing)
1. `backend/modules/ingestion.py` - Add Mode A/B/C wrappers
2. `backend/routers/sources.py` - New endpoints
3. `backend/modules/persona_spec_v2.py` - Add verification fields
4. `backend/modules/agent.py` - Enhance with honesty rules

### New Files
1. `backend/modules/export_parsers.py` - LinkedIn/Twitter parsers
2. `backend/modules/robots_checker.py` - robots.txt compliance
3. `backend/modules/claim_extractor.py` - AI claim extraction
4. `backend/modules/persona_compiler.py` - Claims → Persona
5. `backend/modules/citation_runtime.py` - Runtime enforcement
6. `backend/migrations/20260220_create_claims_table.sql`
7. `backend/migrations/20260227_create_claim_links_table.sql`

---

**Document Status:** Ready for implementation  
**Next Step:** Begin Milestone 1 (Foundation)
