# Architecture Reference: Ingestion & Retrieval Pipeline

**System:** Verified Digital Twin Brains  
**Version:** 1.0.0  
**Last Updated:** 2026-02-09  
**Commit:** `fe03d5f6441ae830cc1d10d300475c14faf11e91`  

---

## 1. System Overview

This document describes the end-to-end architecture for:
1. **Ingestion Pipeline**: Content ingestion (files, URLs) → chunking → embeddings → vector storage
2. **Retrieval Pipeline**: Query processing → vector search → reranking → context assembly

### 1.1 Architecture Principles

| Principle | Implementation |
|-----------|----------------|
| Multi-tenancy | Pinecone namespace = `twin_id`; all queries filtered by twin |
| Async processing | Worker-based job queue with Redis (preferred) or DB fallback |
| Idempotency | Content hash deduplication; chunk cleanup before re-indexing |
| Observability | Step-by-step diagnostics in `source_events` table |
| Graceful degradation | Multiple fallback strategies for external APIs (YouTube, X) |

---

## 2. Ingestion Pipeline Architecture

### 2.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE FLOW                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │   Frontend   │───▶│   Backend    │───▶│    Queue     │───▶│  Worker   │ │
│  │   Handler    │    │   Router     │    │   (Job)      │    │  Process  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│         │                   │                   │                 │         │
│         ▼                   ▼                   ▼                 ▼         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │ UnifiedIngest│    │ ingestion.py │    │ training_jobs│    │ process_  │ │
│  │ ion.tsx      │    │ (router)     │    │ .py (queue)  │    │ training_ │ │
│  │              │    │              │    │              │    │ job()     │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └─────┬─────┘ │
│                                                                     │       │
│                                                                     ▼       │
│                                                              ┌───────────┐  │
│                                                              │ingestion. │  │
│                                                              │py:process_│  │
│                                                              │and_index_ │  │
│                                                              │text()     │  │
│                                                              └─────┬─────┘  │
│                                                                    │        │
│                              ┌────────────────────────────────────┼────┐   │
│                              ▼                                    ▼    │   │
│                       ┌──────────┐                          ┌────────┐  │   │
│                       │ Pinecone │                          │Chunks  │  │   │
│                       │(vectors) │                          │(Supa-  │  │   │
│                       │namespace:│                          │base)   │  │   │
│                       │twin_id   │                          └────────┘  │   │
│                       └──────────┘                                      │   │
│                                                                         │   │
│                       ┌──────────┐                                      │   │
│                       │ Sources  │◀─────────────────────────────────────┘   │
│                       │ (metadata)│                                         │
│                       └──────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Reference

#### Frontend Entry Points

| Component | File | Purpose |
|-----------|------|---------|
| `UnifiedIngestion` | `frontend/components/ingestion/UnifiedIngestion.tsx` | Main ingestion UI |
| `useJobPolling` | `frontend/lib/hooks/useJobPolling.ts` | Job status polling hook |

**Key Functions:**
```typescript
// UnifiedIngestion.tsx:101
handleIngest()          // URL ingestion flow
handleFileSelect()      // File upload flow (line 182)
handleDrop()            // Drag-and-drop upload (line 237)
```

#### Backend Routers

| Route | Handler | File | Line |
|-------|---------|------|------|
| `POST /ingest/file/{twin_id}` | `ingest_file_endpoint` | `routers/ingestion.py` | 130 |
| `POST /ingest/url/{twin_id}` | `ingest_url_endpoint` | `routers/ingestion.py` | 254 |
| `POST /ingest/youtube/{twin_id}` | `ingest_youtube` | `routers/ingestion.py` | 64 |
| `POST /ingest/podcast/{twin_id}` | `ingest_podcast` | `routers/ingestion.py` | 86 |
| `POST /ingest/x/{twin_id}` | `ingest_x` | `routers/ingestion.py` | 108 |
| `GET /training-jobs/{job_id}` | `get_training_job_endpoint` | `routers/ingestion.py` | 390 |
| `POST /training-jobs/{job_id}/retry` | `retry_training_job_endpoint` | `routers/ingestion.py` | 424 |

#### Processing Modules

| Module | File | Purpose |
|--------|------|---------|
| Job Queue | `modules/job_queue.py` | Redis/DB queue abstraction |
| Training Jobs | `modules/training_jobs.py` | Job lifecycle management |
| Ingestion | `modules/ingestion.py` | Content extraction & indexing |
| Embeddings | `modules/embeddings.py` | OpenAI embedding generation |

#### Worker

| Component | File | Purpose |
|-----------|------|---------|
| Worker Loop | `worker.py:34` | Background job processor |
| Job Dispatcher | `worker.py:71-84` | Routes jobs by type |

### 2.3 Data Contracts

#### Request: File Upload
```typescript
// POST /ingest/file/{twin_id}
// Content-Type: multipart/form-data

{
  file: File  // PDF, DOCX, XLSX, TXT
}

// Headers:
// Authorization: Bearer {jwt_token}
```

#### Request: URL Ingestion
```typescript
// POST /ingest/{type}/{twin_id}
// Content-Type: application/json

{
  url: string  // YouTube, X/Twitter, Podcast RSS, Generic URL
}

// Headers:
// Authorization: Bearer {jwt_token}
```

#### Response: Ingestion Initiated
```typescript
{
  source_id: string;   // UUID for tracking
  job_id: string;      // Queue job ID
  status: "pending" | "processing"
}
```

#### Job Record (training_jobs table)
```typescript
interface TrainingJob {
  id: string;
  source_id: string;
  twin_id: string;
  status: "queued" | "processing" | "complete" | "failed" | "needs_attention";
  job_type: "ingestion" | "reindex" | "health_check";
  priority: number;           // Higher = processed first
  metadata: {
    provider: string;         // youtube, x, podcast, web, file
    url?: string;
    correlation_id?: string;
    ingest_mode: "ingest" | "retry";
  };
  error_message?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}
```

#### Source Record (sources table)
```typescript
interface Source {
  id: string;
  twin_id: string;
  filename: string;
  file_size: number;
  content_text: string;       // Extracted text
  content_hash: string;       // SHA-256 for deduplication
  status: "pending" | "processing" | "live" | "error";
  staging_status: "staged" | "live";
  health_status: "healthy" | "warning" | "failed";
  chunk_count: number;
  extracted_text_length: number;
  citation_url?: string;
  last_error?: object;        // Structured error info
  last_step?: string;         // Current/last processing step
  created_at: string;
  updated_at: string;
}
```

#### Chunk Record (chunks table)
```typescript
interface Chunk {
  id: string;                 // UUID
  source_id: string;          // Parent source
  content: string;            // Text content
  vector_id: string;          // Pinecone vector ID
  metadata: {
    synthetic_questions: string[];
    category: "FACT" | "OPINION";
    tone: string;
    opinion_topic?: string;
    opinion_stance?: string;
    opinion_intensity?: number;
  };
  created_at: string;
}
```

#### Vector Metadata (Pinecone)
```typescript
interface VectorMetadata {
  source_id: string;
  twin_id: string;
  chunk_id: string;           // Links to chunks table
  text: string;               // Original chunk text
  synthetic_questions: string[];
  category: "FACT" | "OPINION";
  tone: string;
  opinion_topic?: string;
  opinion_stance?: string;
  opinion_intensity?: number;
  is_verified: boolean;       // false for regular sources
  filename?: string;
  type?: string;              // youtube, x_thread, pdf, etc.
  url?: string;
  video_id?: string;          // YouTube only
  tweet_id?: string;          // X only
}
```

### 2.4 Processing Steps

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     INGESTION PROCESSING STEPS                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 1: QUEUED                                                             │
│  ├── Source row created with status="pending"                               │
│  └── Job enqueued to training_jobs queue                                    │
│                                                                             │
│  Step 2: FETCHING (URL sources only)                                        │
│  ├── YouTube: transcript extraction via youtube-transcript-api → yt-dlp    │
│  ├── X/Twitter: Syndication API → Nitter → FxTwitter → VxTwitter           │
│  ├── Podcast: RSS fetch → audio download → transcription                    │
│  ├── LinkedIn: OpenGraph metadata only (public)                            │
│  └── Web: httpx fetch → BeautifulSoup text extraction                       │
│                                                                             │
│  Step 3: PARSED                                                             │
│  ├── Text extracted from source                                            │
│  ├── content_hash calculated (SHA-256)                                     │
│  └── sources row updated: content_text, status="processing"                │
│                                                                             │
│  Step 4: CHUNKED                                                            │
│  ├── chunk_text() splits text: 1000 chars, 200 overlap                     │
│  └── Old chunks deleted for idempotency                                     │
│                                                                             │
│  Step 5: EMBEDDED                                                           │
│  ├── analyze_chunk_content() → GPT-4o-mini generates:                      │
│  │   ├── 3 synthetic questions                                             │
│  │   ├── category (FACT/OPINION)                                           │
│  │   ├── tone                                                              │
│  │   └── opinion_map (if applicable)                                       │
│  ├── get_embedding() → text-embedding-3-large (3072-dim)                   │
│  └── Enriched text: "CONTENT: {chunk}\nQUESTIONS: {questions}"              │
│                                                                             │
│  Step 6: INDEXED                                                            │
│  ├── Chunks inserted to Supabase chunks table                              │
│  ├── Vectors upserted to Pinecone (namespace=twin_id)                      │
│  └── Default group permission granted (content_permissions table)          │
│                                                                             │
│  Step 7: LIVE                                                               │
│  ├── sources row updated: status="live", staging_status="live"             │
│  └── training_jobs row updated: status="complete"                          │
│                                                                             │
│  Graph Extraction (Async - optional)                                        │
│  └── enqueue_content_extraction_job() → Scribe Engine                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.5 Security Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SECURITY CHECKS                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: Authentication                                                    │
│  └── JWT token validated via verify_owner() or get_current_user()          │
│                                                                             │
│  Layer 2: Twin Ownership                                                    │
│  └── verify_twin_ownership(twin_id, user) → checks tenant_id match         │
│      File: modules/auth_guard.py                                            │
│                                                                             │
│  Layer 3: Source Ownership                                                  │
│  └── verify_source_ownership(source_id, user) → returns twin_id            │
│      Used in: extract-nodes, retry, delete endpoints                        │
│                                                                             │
│  Layer 4: Data Isolation                                                    │
│  ├── Pinecone: namespace = twin_id (hard isolation)                        │
│  ├── Supabase: RLS policies on sources, chunks (twin_id filter)            │
│  └── Query: All queries include .eq("twin_id", twin_id)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.6 Error Handling

#### Error Structure (sources.last_error)
```typescript
interface IngestionError {
  code: string;              // YOUTUBE_TRANSCRIPT_UNAVAILABLE, X_BLOCKED, etc.
  message: string;           // User-facing message
  provider: string;          // youtube, x, podcast, web, file
  step: string;              // fetching, parsed, chunked, embedded, indexed
  provider_error_code?: string;
  http_status?: number;
  correlation_id?: string;
  raw: object;               // Debug info
  traceback?: string;        // Server-side stack trace
}
```

#### Common Error Codes

| Code | Description | Retryable |
|------|-------------|-----------|
| `YOUTUBE_TRANSCRIPT_UNAVAILABLE` | No captions or extraction failed | No |
| `X_BLOCKED_OR_UNSUPPORTED` | X/Twitter blocked scraper | No |
| `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH` | Login wall encountered | No |
| `FILE_EXTRACTION_EMPTY` | PDF has no selectable text | No |
| `FILE_EXTRACTION_FAILED` | PDF/DOCX parse error | No |
| `WEB_FETCH_FAILED` | HTTP error fetching URL | Yes (transient) |
| `CHUNKING_FAILED` | Text processing error | No |
| `EMBEDDINGS_FAILED` | OpenAI API error | Yes |
| `INDEXING_FAILED` | Pinecone/Supabase error | Yes |

---

## 3. Retrieval Pipeline Architecture

### 3.1 Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RETRIEVAL PIPELINE FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐                                                           │
│  │ User Query   │                                                           │
│  └──────┬───────┘                                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │           retrieve_context_with_verified_first()                    │   │
│  │                     retrieval.py:392                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                   │
│         ├──▶ STEP 1: Verified QnA Lookup (2s timeout)                      │
│         │    └── match_verified_qna() → modules/verified_qna.py           │
│         │        If similarity >= 0.7: return immediately                  │
│         │                                                                   │
│         └──▶ STEP 2: Vector Retrieval                                      │
│              └── retrieve_context_vectors() → retrieval.py:433            │
│                  │                                                          │
│                  ├── expand_query() → GPT-4o-mini (3 variations)          │
│                  ├── generate_hyde_answer() → Hypothetical answer         │
│                  ├── get_embeddings_async() → 3072-dim vectors            │
│                  ├── _execute_pinecone_queries()                          │
│                  │   ├── Verified search: top_k=5, is_verified=true       │
│                  │   └── General search: top_k=20, no filter              │
│                  ├── rrf_merge() → Reciprocal Rank Fusion                 │
│                  ├── _filter_by_group_permissions()                       │
│                  ├── _deduplicate_and_limit()                             │
│                  └── FlashRank reranking (ms-marco-MiniLM-L-12-v2)        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Output: List[Context]                                               │   │
│  │                                                                     │   │
│  │ {                                                                   │   │
│  │   text: string,              // Chunk content                       │   │
│  │   score: number,             // Reranker score                      │   │
│  │   source_id: string,         // Citation reference                  │   │
│  │   chunk_id: string,          // Chunk UUID                          │   │
│  │   is_verified: boolean,      // From verified_qna                 │   │
│  │   category: "FACT" | "OPINION",                                     │   │
│  │   tone: string,                                                     │   │
│  │   citation_url?: string,     // Original source URL                 │   │
│  │   verified_qna_match?: boolean                                     │   │
│  │ }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Reference

#### Entry Points

| Route | Handler | File | Purpose |
|-------|---------|------|---------|
| `POST /chat/{twin_id}` | `chat` | `routers/chat.py:256` | Owner chat with streaming |
| `POST /chat-widget/{twin_id}` | `chat_widget` | `routers/chat.py:775` | Public widget chat |
| `POST /public/chat/{twin_id}/{token}` | `public_chat_endpoint` | `routers/chat.py:1058` | Public share links |

#### Retrieval Modules

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `retrieve_context` | `modules/retrieval.py` | 560 | Main entry point (wrapper) |
| `retrieve_context_with_verified_first` | `modules/retrieval.py` | 392 | Verified QnA + vector search |
| `retrieve_context_vectors` | `modules/retrieval.py` | 433 | Pure vector retrieval |
| `expand_query` | `modules/retrieval.py` | 47 | Query variation generation |
| `generate_hyde_answer` | `modules/retrieval.py` | 73 | HyDE generation |
| `rrf_merge` | `modules/retrieval.py` | 98 | Reciprocal Rank Fusion |

#### Agent Integration

| Component | File | Purpose |
|-----------|------|---------|
| `run_agent_stream` | `modules/agent.py:670` | LangGraph agent execution |
| `retrieve_hybrid_node` | `modules/agent.py:602` | Retrieval node in graph |
| `get_retrieval_tool` | `modules/tools.py` | Tool wrapper for retrieval |

### 3.3 Data Contracts

#### Retrieval Request
```typescript
interface RetrievalRequest {
  query: string;
  twin_id: string;
  group_id?: string;        // For permission filtering
  top_k: number;            // Default: 5
}
```

#### Retrieval Response (Context)
```typescript
interface RetrievalContext {
  text: string;             // The chunk text
  score: number;            // Final reranker score
  source_id: string;        // Source UUID for citations
  chunk_id: string;         // Chunk UUID
  is_verified: boolean;     // From verified_qna table
  verified_qna_match?: boolean;  // True if direct QnA match
  category: "FACT" | "OPINION";
  tone: string;
  opinion_topic?: string;
  opinion_stance?: string;
  opinion_intensity?: number;
  rrf_score?: number;       // Pre-reranker score
  citation_url?: string;    // From sources table
}
```

#### Streaming Response (Chat)
```typescript
// Event 1: Metadata
{
  type: "metadata";
  citations: string[];                    // Source IDs
  citation_details: {                     // Resolved source info
    id: string;
    filename: string;
    citation_url?: string;
  }[];
  confidence_score: number;
  conversation_id: string;
  owner_memory_refs: string[];
  owner_memory_topics: string[];
  teaching_questions?: string[];
  planning_output?: object;
  dialogue_mode: string;
  intent_label: string;
  module_ids: string[];
  graph_context: {
    has_graph: boolean;
    node_count: number;
    graph_used: boolean;
  };
}

// Event 2+: Content tokens
{
  type: "content";
  token: string;      // Accumulated text
  content: string;    // Same as token
}

// Final Event: Done
{
  type: "done";
}

// Alternative: Clarification needed
{
  type: "clarify";
  clarification_id: string;
  question: string;
  options?: { label: string; value: string }[];
  memory_write_proposal?: object;
  status: "pending_owner";
}
```

### 3.4 Reranking Strategy

```python
# FlashRank configuration (modules/retrieval.py:13-32)
_ranker_instance = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2",
    cache_dir="./.model_cache"
)

# Reranking logic (modules/retrieval.py:484-515)
if ranker and unique_contexts:
    passages = [
        {"id": str(i), "text": c["text"], "meta": c}
        for i, c in enumerate(unique_contexts)
    ]
    rerank_request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(rerank_request)
    
    # If reranker scores too low (< 0.001), fall back to vector scores
    max_rerank_score = max((float(r.get("score", 0)) for r in results), default=0)
    if max_rerank_score < 0.001:
        final_contexts = unique_contexts[:top_k]  # Use original order
```

### 3.5 Permission Filtering

```python
# _filter_by_group_permissions (modules/retrieval.py:327-362)
def _filter_by_group_permissions(contexts, group_id):
    if not group_id:
        return contexts
    
    # Get allowed source_ids for this group
    permissions_response = supabase.table("content_permissions").select("content_id").eq(
        "group_id", group_id
    ).eq("content_type", "source").execute()
    
    allowed_source_ids = {str(p["content_id"]) for p in permissions_response.data}
    
    # Filter: allow verified memory OR allowed sources
    return [
        c for c in contexts
        if c.get("is_verified") or str(c.get("source_id")) in allowed_source_ids
    ]
```

---

## 4. Configuration Reference

### 4.1 Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SUPABASE_URL` | ✅ | - | Database connection |
| `SUPABASE_SERVICE_KEY` | ✅ | - | Database auth |
| `OPENAI_API_KEY` | ✅ | - | Embeddings & LLM |
| `PINECONE_API_KEY` | ✅ | - | Vector search |
| `PINECONE_INDEX_NAME` | ✅ | - | Vector index |
| `REDIS_URL` | ❌ | - | Job queue (falls back to DB) |
| `DATABASE_URL` | ❌ | - | LangGraph checkpointer (optional) |
| `YOUTUBE_COOKIES_FILE` | ❌ | - | YouTube auth for gated videos |
| `YOUTUBE_PROXY` | ❌ | - | Proxy for YouTube requests |
| `GOOGLE_API_KEY` | ❌ | - | YouTube Data API validation |
| `GRAPH_MEMORY_ENABLED` | ❌ | "false" | Enable graph memory reads/writes |
| `ENABLE_ENHANCED_INGESTION` | ❌ | "false" | Enable enhanced routes |

### 4.2 Tunable Parameters

| Parameter | File | Default | Description |
|-----------|------|---------|-------------|
| `chunk_size` | `ingestion.py:1683` | 1000 | Text chunk size |
| `chunk_overlap` | `ingestion.py:1683` | 200 | Chunk overlap |
| `top_k` | `retrieval.py:396` | 5 | Retrieved contexts |
| `verified_qna_timeout` | `retrieval.py:414` | 2.0s | Verified lookup timeout |
| `pinecone_timeout` | `retrieval.py:457` | 20.0s | Vector search timeout |
| `rerank_threshold` | `retrieval.py:499` | 0.001 | Min reranker score |

---

## 5. Extension Points

### 5.1 Adding a New Ingestion Source

1. **Add provider detection** (`modules/ingestion.py:207`):
```python
def detect_url_provider(url: str) -> str:
    if "newsource.com" in url.lower():
        return "newsource"
```

2. **Add router endpoint** (`routers/ingestion.py`):
```python
@router.post("/ingest/newsource/{twin_id}")
async def ingest_newsource(...):
    # Create source row
    # Queue job
    return {"source_id": ..., "job_id": ..., "status": "pending"}
```

3. **Add worker handler** (`modules/ingestion.py`):
```python
async def ingest_newsource_content(source_id: str, twin_id: str, url: str):
    # Fetch content
    # Extract text
    # Call process_and_index_text()
    pass
```

4. **Add to ingest_url_to_source** (`modules/ingestion.py:1648`):
```python
if detected == "newsource":
    return await ingest_newsource_content(source_id, twin_id, url)
```

### 5.2 Adding a New Retrieval Strategy

1. **Add to retrieve_context_vectors** (`modules/retrieval.py:433`):
```python
# After existing retrieval
new_results = await new_retrieval_method(query, twin_id)
contexts.extend(new_results)
```

2. **Implement the strategy**:
```python
async def new_retrieval_method(query: str, twin_id: str) -> List[Dict]:
    # Custom retrieval logic
    return contexts
```

### 5.3 Custom Chunking Strategy

Replace `chunk_text()` in `modules/ingestion.py:1683`:
```python
def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    # Semantic chunking, sentence boundaries, etc.
    pass
```

---

## 6. Troubleshooting Guide

### 6.1 Job Stuck in "processing"

**Check:**
1. Is worker running? `python worker.py`
2. Check logs: `tail -f worker.log`
3. Check job status: `GET /training-jobs/{job_id}`
4. Force retry: `POST /training-jobs/{job_id}/retry`

### 6.2 Retrieval Returns Empty

**Check:**
1. Sources exist for twin: `GET /sources/{twin_id}`
2. Sources status is "live"
3. Pinecone namespace exists: Check vectors with twin_id namespace
4. Group permissions: `GET /access-groups/{group_id}/permissions`

### 6.3 Citations Not Resolving

**Check:**
1. Source IDs in citations are UUIDs
2. Sources exist in Supabase
3. twin_id filter in citation resolution

### 6.4 Worker Not Processing Jobs

**Check:**
1. Environment variables set in worker process
2. Redis connection (or DB fallback working)
3. Queue length: Check `training_jobs` table for queued jobs

---

## 7. Database Schema

### 7.1 Core Tables

```sql
-- Sources: Metadata for ingested content
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    content_text TEXT DEFAULT '',
    content_hash TEXT,
    status TEXT DEFAULT 'pending', -- pending, processing, live, error
    staging_status TEXT DEFAULT 'staged', -- staged, live
    health_status TEXT DEFAULT 'healthy', -- healthy, warning, failed
    chunk_count INTEGER DEFAULT 0,
    extracted_text_length INTEGER DEFAULT 0,
    citation_url TEXT,
    last_error JSONB,
    last_step TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Training Jobs: Async processing queue
CREATE TABLE training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'queued', -- queued, processing, complete, failed
    job_type TEXT DEFAULT 'ingestion', -- ingestion, reindex, health_check
    priority INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Chunks: Text chunks for citation grounding
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    vector_id TEXT NOT NULL, -- Links to Pinecone
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Content Permissions: Group-based access control
CREATE TABLE content_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID REFERENCES access_groups(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL, -- source, memory, etc.
    content_id UUID NOT NULL,
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Source Events: Step-by-step diagnostics
CREATE TABLE source_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    twin_id UUID REFERENCES twins(id) ON DELETE CASCADE,
    provider TEXT,
    step TEXT, -- queued, fetching, parsed, chunked, embedded, indexed, live
    status TEXT, -- completed, error
    message TEXT,
    metadata JSONB,
    correlation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 8. API Quick Reference

### Ingestion Endpoints

```bash
# File upload
curl -X POST /ingest/file/{twin_id} \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@document.pdf"

# URL ingestion
curl -X POST /ingest/url/{twin_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'

# Check job status
curl /training-jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"

# List sources
curl /sources/{twin_id} \
  -H "Authorization: Bearer $TOKEN"

# Retry failed ingestion
curl -X POST /sources/{source_id}/retry \
  -H "Authorization: Bearer $TOKEN"
```

### Retrieval Endpoints

```bash
# Chat with streaming
curl -X POST /chat/{twin_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are my core principles?",
    "conversation_id": null
  }'

# Debug retrieval
curl -X POST /retrieval \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "test query",
    "twin_id": "uuid",
    "top_k": 5
  }'
```

---

## 9. Change Log

| Date | Change | Commit |
|------|--------|--------|
| 2026-02-09 | Added CORS middleware, /version endpoint, centralized constants | fe03d5f |
| 2026-02-08 | Added source_events diagnostics table | - |
| 2026-02-07 | Added FlashRank reranking | - |
| 2026-02-06 | Added DB fallback for job queue | - |

---

*End of Architecture Reference*
