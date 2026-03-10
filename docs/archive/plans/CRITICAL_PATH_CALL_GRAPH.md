# Critical Path Call Graph

Last updated: 2026-02-04

Scope: re-derived call graph for the critical path from code. Format: user step -> FE file/call site -> backend route -> DB writes/reads -> downstream effects.

**Step 1: Create a digital twin**

- User signs in -> `frontend/app/auth/callback/route.ts` -> `POST /auth/sync-user` -> reads `users`, `tenants`, writes `tenants` and `users` when missing -> establishes tenant_id and onboarding state (`backend/routers/auth.py`).
- User lands in onboarding -> `frontend/lib/context/TwinContext.tsx` + `frontend/app/onboarding/page.tsx` -> `GET /auth/my-twins` -> reads `twins` by tenant_id -> returns existing twins (`backend/routers/auth.py`).
- User creates twin -> `frontend/app/onboarding/page.tsx` and `frontend/app/dashboard/right-brain/page.tsx` -> `POST /twins` -> writes `twins` (tenant_id resolved server-side) -> twin_id becomes canonical namespace for ingestion and retrieval (`backend/routers/twins.py`).
- Optional: user edits twin -> `frontend/app/dashboard/twins/[id]/page.tsx`, `frontend/app/dashboard/settings/page.tsx` -> `PATCH /twins/{twin_id}` -> updates `twins.settings` and metadata -> affects retrieval prompts/visibility (`backend/routers/twins.py`).

**Step 2: Ingest data and produce artifacts**

Ingestion entry points (owner-authenticated)

- Upload file -> `frontend/components/ingestion/UnifiedIngestion.tsx` -> `POST /ingest/file/{twin_id}` -> writes `sources` (status=processing) -> extracts text -> chunks text -> writes `chunks` -> upserts vectors to Pinecone namespace `twin_id` -> updates `sources.status=live` and `chunk_count` -> logs to `ingestion_logs` (`backend/routers/ingestion.py`, `backend/modules/ingestion.py`).
- URL ingest -> `frontend/components/ingestion/UnifiedIngestion.tsx` -> `POST /ingest/url/{twin_id}` -> writes `sources` -> extracts content -> chunks + vectors -> updates `sources` -> logs to `ingestion_logs` (`backend/routers/ingestion.py`, `backend/modules/ingestion.py`).
- YouTube/Podcast/X -> `frontend/components/ingestion/UnifiedIngestion.tsx` -> `POST /ingest/youtube|podcast|x/{twin_id}` -> writes `sources` -> fetches transcripts/content -> chunks + vectors -> updates `sources` -> logs to `ingestion_logs` (`backend/modules/ingestion.py`).

Source visibility and approval

- List sources -> `frontend/app/dashboard/knowledge/page.tsx`, `frontend/app/dashboard/knowledge/staging/page.tsx` -> `GET /sources/{twin_id}` -> reads `sources` (status, staging_status, health_status) -> enables approval/staging UI (`backend/routers/sources.py`).
- Approve source -> `frontend/app/dashboard/knowledge/[source_id]/page.tsx`, `frontend/app/dashboard/knowledge/staging/page.tsx` -> `POST /sources/{source_id}/approve` -> reads `sources`, writes training job (`training_jobs` via `modules.training_jobs.create_training_job`) and updates `sources.staging_status/status` -> downstream job processing (`backend/routers/sources.py`, `backend/modules/ingestion.py`).
- Reject source -> same FE -> `POST /sources/{source_id}/reject` -> updates `sources.staging_status/status`, logs event -> removes from training queue (`backend/routers/sources.py`).
- Bulk approve -> `frontend/app/dashboard/knowledge/staging/page.tsx` -> `POST /sources/bulk-approve` -> batch updates sources and jobs -> accelerates staging (`backend/routers/sources.py`).

Training jobs and processing

- Process queue -> `frontend/app/dashboard/training-jobs/page.tsx` -> `POST /training-jobs/process-queue?twin_id=...` -> reads `training_jobs`, updates job status, writes processed counts -> triggers indexing or downstream extraction based on job type (`backend/routers/ingestion.py`, `backend/modules/training_jobs.py`).
- Job detail -> (missing in FE) `GET /training-jobs/{job_id}` -> reads `training_jobs` -> job state for visibility (`backend/routers/ingestion.py`).

Graph extraction (if enabled)

- Extract nodes -> `frontend/components/ingestion/UnifiedIngestion.tsx` -> `POST /ingest/extract-nodes/{source_id}` -> reads `sources.content_text`, writes `graph_nodes` and `graph_edges` (via Scribe Engine) -> updates `sources.health_status=extracted` (`backend/routers/ingestion.py`, `modules/_core/scribe_engine.py`).
- Graph view -> `frontend/components/Brain/BrainGraph.tsx`, `frontend/app/dashboard/brain/page.tsx` -> `GET /twins/{twin_id}/graph` -> reads `nodes`/`edges` via RPC -> visualizes graph (`backend/routers/graph.py`).
- Graph stats -> `frontend/components/Chat/GraphContext.tsx` -> `GET /twins/{twin_id}/graph-stats` -> reads graph stats -> used for readiness UI (`backend/routers/twins.py`).

Verification readiness

- Publish readiness -> `frontend/components/console/tabs/PublishTab.tsx` -> `GET /twins/{twin_id}/verification-status` -> reads Pinecone stats (vector count), graph stats, and `twin_verifications` -> returns readiness (`backend/routers/twins.py`).
- Verify retrieval -> `frontend/components/console/tabs/ChatTab.tsx` -> `POST /verify/twins/{twin_id}/run` -> reads `sources`, `chunks`, hits retrieval -> writes `twin_verifications` (`backend/routers/verify.py`).

**Step 3: Public retrieval (share link and widget)**

Share link creation

- Generate share link -> `frontend/app/dashboard/settings/page.tsx` -> `GET/POST /twins/{twin_id}/share-link` and `PATCH /twins/{twin_id}/sharing` -> reads/writes `share_links` or `twins.settings` (public_share_enabled) -> yields share token used in public access (`backend/routers/auth.py`, `modules/share_links.py`).

Public share validation

- Open share page -> `frontend/app/share/[twin_id]/[token]/page.tsx` -> `GET /public/validate-share/{twin_id}/{token}` -> validates token, may read `share_links` -> determines if public chat is allowed (`backend/routers/auth.py`).

Public share chat (non-widget)

- Send public message -> `frontend/app/share/[twin_id]/[token]/page.tsx` -> `POST /public/chat/{twin_id}/{token}` -> validates token -> optional identity gate -> reads Pinecone vectors and `chunks` for retrieval -> returns `{status:"answer"}` or `{status:"queued"}` for clarifications; may create clarification thread in `clarifications` (`backend/routers/chat.py`, `modules/retrieval.py`, `modules/owner_memory_store.py`).

Public widget chat

- Widget message -> `frontend/public/widget.js` -> `POST /chat-widget/{twin_id}` with `api_key` -> validates API key and domain -> creates/updates `sessions`, creates/updates `conversations`, logs messages -> reads Pinecone vectors and `chunks` -> streams response events (`backend/routers/chat.py`, `modules/sessions.py`, `modules/observability.py`, `modules/retrieval.py`).

**Downstream Artifacts and Effects Summary**

- `sources` rows: created by ingestion; updated with status, staging_status, health_status, chunk_count, metadata.
- `chunks` rows: created per ingestion; store content and vector IDs for citation grounding.
- Pinecone vectors: upserted per chunk in namespace `twin_id`; used for retrieval in public chat.
- `graph_nodes`/`graph_edges`: created by extract-nodes (explicit) or other graph jobs; used by graph UI and readiness checks.
- `conversations`/`messages`: created in owner chat and widget chat; public share chat does not create a conversation by default.
- `clarifications` and `owner_memory`: created when identity gate requires clarification; resolved by owner via `/twins/{twin_id}/clarifications/{id}/resolve`.