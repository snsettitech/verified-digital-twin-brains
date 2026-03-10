# Persona Pipeline Audit (Evidence-Based)

## Scope
This audit maps the current ingestion, retrieval, and chat execution paths and proposes safe insertion points for a feature-flagged Persona Extraction + Identity Fast-Path system with default behavior unchanged.

## 1) Current Codebase Map

### Ingestion entrypoints
- `backend/routers/ingestion.py:207` `POST /ingest/youtube/{twin_id}`
- `backend/routers/ingestion.py:229` `POST /ingest/podcast/{twin_id}`
- `backend/routers/ingestion.py:251` `POST /ingest/x/{twin_id}`
- `backend/routers/ingestion.py:273` `POST /ingest/file/{twin_id}`
- `backend/routers/ingestion.py:443` `POST /ingest/url/{twin_id}`
- These routes queue jobs via `create_training_job` and `enqueue_job` (`backend/routers/ingestion.py:193`, `backend/modules/training_jobs.py:14`, `backend/modules/job_queue.py:73`).

### Normalization/parsing/transcription outputs
- File/url parsing and extraction are performed in `backend/modules/ingestion.py` provider-specific functions and routed into `process_and_index_text` (`backend/modules/ingestion.py:1927`).
- Source label metadata is persisted at ingest-time (`backend/routers/ingestion.py:129`).

### Chunking logic
- Fixed-size chunking exists in `chunk_text` (`backend/modules/ingestion.py:1802`).
- Metadata-aware chunking exists in `chunk_text_with_metadata` (`backend/modules/ingestion.py:1839`).
- `process_and_index_text` uses `chunk_text_with_metadata` by default (`backend/modules/ingestion.py:1946`).

### Pinecone upsert path
- Pinecone client/index is initialized in `get_pinecone_index` (`backend/modules/clients.py:138`) using `PINECONE_INDEX_NAME` and optional `PINECONE_HOST` (`backend/modules/clients.py:142`, `backend/modules/clients.py:143`).
- Ingestion creates embeddings (vector mode) and upserts through adapter:
  - Adapter creation: `backend/modules/ingestion.py:2004`
  - Embedding call: `backend/modules/ingestion.py:2059`
  - Upsert call: `backend/modules/ingestion.py:2130`
- Adapter supports vector/integrated modes:
  - mode resolution: `backend/modules/pinecone_adapter.py:41`
  - integrated text field config: `backend/modules/pinecone_adapter.py:54`
  - adapter class: `backend/modules/pinecone_adapter.py:57`

### Retrieval + rerank path
- Retrieval wrapper: `retrieve_context` (`backend/modules/retrieval.py:2561`).
- Main vector retrieval pipeline: `retrieve_context_vectors` (`backend/modules/retrieval.py:2188`).
- Pinecone query via adapter: `backend/modules/retrieval.py:1666`, `backend/modules/retrieval.py:1756`.
- Reranker entrypoint: `rerank_contexts` (`backend/modules/retrieval.py:1213`) with Cohere model env default `rerank-v3.5` (`backend/modules/retrieval.py:886`).

### Chat request handling/router
- Private chat endpoint: `backend/routers/chat.py:1495` (`POST /chat/{twin_id}`).
- Widget/public chat endpoints: `backend/routers/chat.py:2208`, `backend/routers/chat.py:2654`.
- Router delegates to `run_agent_stream` (`backend/routers/chat.py:1708`, `backend/routers/chat.py:2395`, `backend/routers/chat.py:2833`).
- Agent graph runtime starts in `run_agent_stream` (`backend/modules/agent.py:2440`) and uses:
  - `router_node` (`backend/modules/agent.py:759`)
  - `retrieve_hybrid_node` (`backend/modules/agent.py:2358`)
  - `planner_node` (`backend/modules/agent.py:1765`)
  - `realizer_node` (`backend/modules/agent.py:2171`)

### Onboarding/twin creation flow
- Sync/auth + tenant bootstrap: `/auth/sync-user` (`backend/routers/auth.py:149`).
- My twins: `/auth/my-twins` (`backend/routers/auth.py:324`).
- Twin create: `/twins` (`backend/routers/twins.py:94`).

### DB models/tables relevant to sources and metadata
- `twins.settings` JSONB exists and is already used for runtime persona/system settings (`backend/database/schema/supabase_schema.sql:34`).
- Core source/chunk tables:
  - `sources` (`backend/database/schema/supabase_schema.sql:49`)
  - `chunks` (`backend/database/schema/supabase_schema.sql:61`)
- Runtime review queue already exists:
  - `owner_review_queue` table (`backend/database/migrations/20260217_twin_runtime_governance.sql:51`)
  - helper enqueue function (`backend/modules/runtime_audit_store.py:99`)

### Job queue/background workers
- Queue abstraction with Redis + DB fallback: `backend/modules/job_queue.py:73`.
- Worker loop and dispatch: `backend/worker.py:119`.
- Ingestion job processing entrypoint: `backend/modules/training_jobs.py:118`.

## 2) Recommended Insertion Points

### Persona extraction pipeline
- Insert best-effort extraction hook at end of ingestion indexing (`backend/modules/ingestion.py` right after successful upsert around `2130-2175`), so extraction runs only after source content is normalized/chunked and persisted.
- Keep extraction non-blocking for ingestion success (log-only on extraction errors).

### Canonical persona profile storage
- Reuse `twins.settings` as storage envelope for canonical persona profile + extraction candidates to avoid schema migration.
- Suggested keys:
  - `persona_identity_pack` (canonical)
  - `persona_extraction_candidates` (raw candidates with confidence/evidence/provenance)
- Reuse `owner_review_queue` for low-confidence candidate review events.

### Intent router + fast-path responses
- Insert pre-retrieval fast-path check inside `router_node` (`backend/modules/agent.py:759`) after query normalization/rewrite and before retrieval policy execution.
- Return `requires_evidence=False` only on fast-path hit when profile is eligible; otherwise keep current retrieval-first behavior.
- Build deterministic fast-path response in planner short-circuit branch before answerability/retrieval-dependent logic (`backend/modules/agent.py:1765`).

### Owner approval/review flow
- Reuse `profile_status` in canonical profile (`draft`/`approved`).
- Fast-path eligibility gate:
  - only `approved` by default
  - allow `draft` only with explicit env override
- Low-confidence extraction facts enqueue review items via existing `owner_review_queue`.

## 3) Risk Analysis

### What can break
- Chat behavior drift if fast-path mistakenly activates without explicit enablement.
- Ingestion latency increase if extraction is heavy/blocking.
- Incorrect persona claims if low-confidence facts are auto-promoted.
- Runtime exceptions in ingestion or agent if new modules fail.

### Regression controls
- All new behavior behind feature flags defaulting to `false`.
- Extraction path wrapped in try/except and non-fatal.
- Fast-path only executes when:
  - fast-path flag is on
  - intent is matched
  - canonical profile exists and approval policy passes
- Preserve existing response shapes (`planning_output`, `routing_decision`, `AIMessage.additional_kwargs`) to avoid frontend contract breakage.

## 4) Rollout Plan (Feature-Flagged + Rollback)

### Phase 1 (dark launch)
- Deploy code with:
  - `PERSONA_EXTRACTION_ENABLED=false`
  - `PERSONA_FASTPATH_ENABLED=false`
  - `PERSONA_DRAFT_PROFILE_ALLOWED=false`
- Verify baseline tests unchanged.

### Phase 2 (extraction only)
- Enable `PERSONA_EXTRACTION_ENABLED=true` only.
- Validate candidates are populated and low-confidence items appear in owner review queue.
- Keep chat behavior unchanged (`PERSONA_FASTPATH_ENABLED=false`).

### Phase 3 (fast-path pilot)
- Enable `PERSONA_FASTPATH_ENABLED=true` for selected tenants/twins.
- Keep `PERSONA_DRAFT_PROFILE_ALLOWED=false` to require approved profile.
- Monitor hit/miss logs and fallback correctness.

### Rollback
- Set all persona flags to `false` (no schema rollback required).
- System returns to existing RAG-only behavior immediately.
