# Link-First Persona Compiler - Quick Reference

## 3-Mode Ingestion Matrix

| Mode | Input | Platforms | Implementation | Reuses |
|------|-------|-----------|----------------|--------|
| **A** | Export Upload | LinkedIn, Twitter/X | `ingest_linkedin_export()` | `ingestion.py` + custom parsers |
| **B** | Paste/Import | Private docs, Slack | `ingest_pasted_content()` | `ingestion.py` direct |
| **C** | Web Fetch | GitHub, Blogs | `ingest_public_url()` | `ingest_web_url()` + robots.txt |

## Database Impact

```
NEW TABLES (2):
├── claims              # Atomic statements from chunks
│   ├── id, twin_id, claim_text, claim_type
│   ├── source_chunk_ids[]  # ← Stable citations
│   ├── confidence_score, verification_status
│   └── extracted_at, extraction_version
│
└── claim_links         # Claims → Persona layers
    ├── id, claim_id, persona_spec_id
    ├── layer_name, claim_role
    └── verification_required  # ← Layer 2/3 default TRUE

REUSED (0 changes):
├── sources table       # Existing - no changes
├── chunks table        # Existing - no changes  
└── persona_specs table # JSONB spec - no schema change
```

## Key Code Locations

### Verified Call Chain
```
onboarding/page.tsx:261      → POST /api/twins
twins.py:193-239             → create_twin() + bootstrap
persona_bootstrap.py:25-70   → bootstrap_persona_from_onboarding()
persona_spec_store_v2.py:121 → get_active_persona_spec_v2()
agent.py:351-369             → build_system_prompt_with_trace()
agent.py:461-532             → _build_prompt_from_v2_persona()
```

### Inference Honesty Defaults
```python
# persona_spec_v2.py
class CognitiveHeuristic(BaseModel):
    verification_required: bool = True  # Layer 2

class ValueItem(BaseModel):
    verification_required: bool = True  # Layer 3
```

### Existing Ingestion Stack (Reuse)
```
ingestion.py:
├── ingest_file()           # PDF/DOCX handling
├── ingest_url()            # Generic URL
├── ingest_web_url()        # Web scraping
├── ingest_youtube_transcript()
├── process_and_index_text() # Chunk + embed + Pinecone
└── chunk_text()            # Chunking logic
```

## Implementation Order

```
Week 1: Foundation
├── export_parsers.py       # LinkedIn/Twitter parsers
├── robots_checker.py       # robots.txt compliance
├── ingestion.py additions  # Mode A/B/C wrappers
└── routers/sources.py      # New endpoints

Week 2: Claim Extraction
├── claim_extractor.py      # AI chunk → claims
└── migration: claims table

Week 3: Persona Compiler
├── persona_compiler.py     # Claims → 5-Layer
├── persona_spec_v2.py      # Add verification fields
└── migration: claim_links table

Week 4: Citation Runtime
├── citation_runtime.py     # Response enforcement
└── agent.py integration    # Honesty rules in prompt
```

## Citation Format

```
Response: "I prioritize B2B investments over B2C."
Cited:    "I prioritize B2B investments [LinkedIn post, 2024; 
           Internal doc, Q1 2023]"

Storage:
  claim.claim_text = "Prefers B2B over B2C"
  claim.source_chunk_ids = [chunk_1_id, chunk_2_id]
  claim.verification_status = 'confirmed'
```

## Safety Rules

| Platform | Default Behavior |
|----------|-----------------|
| LinkedIn | Mode A only (exports) - NO scraping |
| Twitter/X | Mode A only (exports) - NO API scraping |
| GitHub | Mode C allowed - check robots.txt |
| Personal Blogs | Mode C allowed - check robots.txt |
| Private Sources | Mode B only (owner upload/paste) |

## Configuration

```python
# .env
ROBOTS_TXT_CACHE_TTL=3600      # Cache robots.txt for 1 hour
WEB_FETCH_RATE_LIMIT=1.0       # 1 second between requests
MAX_EXPORT_FILE_SIZE=50MB      # Upload limit
CLAIM_EXTRACTION_MODEL=gpt-4o  # AI model for claim extraction
```
