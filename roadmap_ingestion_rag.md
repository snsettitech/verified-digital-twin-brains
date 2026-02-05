# Roadmap: Document Ingestion + RAG (Epic C)

> Process documents, chunk, embed, and store for retrieval.

## Overview

Full document ingestion pipeline: upload → parse → chunk → embed → store in Pinecone with proper namespace isolation.

## Dependencies

- ✅ Epic A (Auth + Multi-Tenancy)
- ✅ Epic B (Twin Creation)

## Tasks

### C1: Documents Database Schema
**Status**: Not Started
**Estimated**: 2 hours

- [ ] Create migration: 005_documents.sql
- [ ] Add RLS policies
- [ ] Add processing status enum
- [ ] Create chunks table (or embed in vectors)

**Schema**:
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twin_id UUID NOT NULL REFERENCES twins(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    title TEXT NOT NULL,
    content TEXT,
    source_type TEXT NOT NULL, -- 'upload', 'url', 'interview'
    source_url TEXT,
    file_path TEXT,
    metadata JSONB DEFAULT '{}',
    processing_status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    error_message TEXT,
    chunk_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own tenant documents"
ON documents FOR ALL
USING (tenant_id = auth.jwt() ->> 'tenant_id');
```

**Acceptance Criteria**:
- Migration runs successfully
- RLS prevents cross-tenant access
- Status tracking works

---

### C2: Document Upload API
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: C1

- [ ] POST /api/documents/upload - Upload file
- [ ] POST /api/documents/url - Ingest from URL
- [ ] GET /api/documents - List documents
- [ ] GET /api/documents/{id} - Get document status
- [ ] DELETE /api/documents/{id} - Delete document

**Upload Flow**:
1. Frontend gets signed upload URL
2. Frontend uploads to Supabase Storage
3. Frontend calls API with file path
4. API queues processing job

**Acceptance Criteria**:
- Files upload to Supabase Storage
- Processing status updates in real-time
- Proper error handling

---

### C3: Document Parser Service
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: C2

- [ ] Create parser for PDF (PyPDF2 or pdfplumber)
- [ ] Create parser for DOCX (python-docx)
- [ ] Create parser for TXT/MD
- [ ] Extract metadata (title, author, date)
- [ ] Handle encoding issues

**Acceptance Criteria**:
- All supported formats parse correctly
- Metadata extracted when available
- Errors logged for failed parses

---

### C4: Chunking Service
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: C3

- [ ] Implement semantic chunking
- [ ] Set chunk size (512 tokens default)
- [ ] Set overlap (50 tokens default)
- [ ] Preserve paragraph boundaries
- [ ] Generate chunk metadata

**Chunking Strategy**:
```python
class ChunkingConfig:
    chunk_size: int = 512
    overlap: int = 50
    split_on: List[str] = ["\n\n", "\n", ". ", " "]
```

**Acceptance Criteria**:
- Chunks are semantically coherent
- Overlap preserves context
- Chunk count stored in document

---

### C5: Embedding Service
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: C4

- [ ] Create OpenAI embedding client
- [ ] Batch embed chunks (max 2048 texts)
- [ ] Handle rate limiting
- [ ] Cache embeddings locally (optional)

**Acceptance Criteria**:
- Embeddings generated for all chunks
- Rate limiting handled gracefully
- Cost tracked per document

---

### C6: Pinecone Integration
**Status**: Not Started
**Estimated**: 4 hours
**Dependencies**: C5

- [ ] Initialize Pinecone client
- [ ] Create upsert function with namespace
- [ ] Namespace format: `{tenant_id}:{twin_id}`
- [ ] Include metadata in vectors:
  - document_id
  - chunk_index
  - title
  - source_type
- [ ] Create delete function for document removal

**Security Requirements**:
- ⚠️ ALWAYS use namespace for isolation
- ⚠️ NEVER query without namespace filter

**Acceptance Criteria**:
- Vectors stored in correct namespace
- Metadata searchable
- Deletion cascades to Pinecone

**Test Plan**:
```python
def test_pinecone_namespace_isolation():
    # Upsert for tenant A
    upsert_vectors("tenant_a:twin_1", vectors_a)

    # Query as tenant B - should find nothing
    results = query_vectors("tenant_b:twin_1", query_vector)
    assert len(results) == 0

    # Query as tenant A - should find vectors
    results = query_vectors("tenant_a:twin_1", query_vector)
    assert len(results) > 0
```

---

### C7: Ingestion Pipeline Orchestrator
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: C3, C4, C5, C6

- [ ] Create async ingestion job
- [ ] Parse → Chunk → Embed → Store pipeline
- [ ] Update document status at each stage
- [ ] Handle failures gracefully
- [ ] Emit events for real-time UI updates

**Pipeline**:
```python
async def ingest_document(document_id: UUID):
    doc = await get_document(document_id)
    await update_status(doc, "processing")

    try:
        content = await parse_document(doc)
        chunks = await chunk_content(content)
        embeddings = await embed_chunks(chunks)
        await store_vectors(doc.twin_id, doc.tenant_id, embeddings)
        await update_status(doc, "completed", chunk_count=len(chunks))
    except Exception as e:
        await update_status(doc, "failed", error=str(e))
```

**Acceptance Criteria**:
- Full pipeline works end-to-end
- Status visible in UI
- Failures are recoverable

---

### C8: Vector Search API
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: C6

- [ ] POST /api/search - Search vectors
- [ ] Include metadata filters
- [ ] Return chunk text + document info
- [ ] Enforce namespace from JWT

**Request/Response**:
```python
class SearchRequest(BaseModel):
    twin_id: UUID
    query: str
    top_k: int = 5
    filters: Optional[Dict] = None

class SearchResult(BaseModel):
    chunk_text: str
    document_id: UUID
    document_title: str
    score: float
```

**Acceptance Criteria**:
- Search returns relevant results
- Namespace enforced
- Filters work correctly

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| C1 | Not Started | | |
| C2 | Not Started | | |
| C3 | Not Started | | |
| C4 | Not Started | | |
| C5 | Not Started | | |
| C6 | Not Started | | |
| C7 | Not Started | | |
| C8 | Not Started | | |
