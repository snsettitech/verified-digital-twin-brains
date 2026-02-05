# Critical Path Execution Plan

Last updated: 2026-02-04

This plan executes in vertical slices, smallest reliable change first. No refactors or deletions before the contract and drift docs are complete.

1. Align onboarding + twin creation contracts

Scope: fix `/ingest/document`, `/ingest/url` mismatches and missing verified QnA creation. Decide whether to change FE to match BE or add BE routes.

Files impacted: `frontend/app/onboarding/page.tsx`, `backend/routers/ingestion.py`, `backend/routers/knowledge.py`, `backend/modules/schemas.py`.

Dependencies: confirm intended onboarding flow and whether verified QnA seeding is required.

Risks: breaking onboarding for existing users if route changes are inconsistent.

Acceptance checks: onboarding can create a twin, ingest a URL, and complete without 404s; network calls align with documented schemas.

2. Fix chat contract drift for preview and widget

Scope: standardize request shape to `ChatRequest { query }` and standardize stream event shape for `/chat` and `/chat-widget`. Update FE preview and widget parsing accordingly.

Files impacted: `frontend/components/onboarding/steps/PreviewTwinStep.tsx`, `frontend/public/widget.js`, `backend/routers/chat.py`, `backend/modules/schemas.py`.

Dependencies: agree on canonical stream event schema (`metadata`, `content`, `clarify`, `done`, `error`).

Risks: breaking public widget or owner chat if stream parsing is inconsistent.

Acceptance checks: preview chat works; widget renders streamed replies; clarify events handled correctly.

3. Ingestion status and artifact contracts

Scope: align `/sources/{source_id}/health`, `/sources/{source_id}/reject`, `/sources/bulk-approve`, `/ingest/extract-nodes` responses and request bodies. Add or align `/training-jobs` list and retry or remove FE usage.

Files impacted: `backend/routers/sources.py`, `backend/routers/ingestion.py`, `frontend/app/dashboard/knowledge/[source_id]/page.tsx`, `frontend/app/dashboard/knowledge/staging/page.tsx`, `frontend/components/ingestion/UnifiedIngestion.tsx`, `frontend/app/dashboard/training-jobs/page.tsx`.

Dependencies: decide canonical training-job listing API (new endpoint or FE change).

Risks: ingestion UI regressions and job queue handling.

Acceptance checks: source health renders; reject/bulk approve succeed; graph extraction returns expected fields; training jobs list shows without 404s.

4. Enforce authenticated fetch usage for critical endpoints

Scope: replace raw `fetch` calls with `useAuthFetch` for owner-only routes (chat, metrics, verify, debug). Ensure public routes do not require bearer tokens.

Files impacted: `frontend/components/console/tabs/ChatTab.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/app/dashboard/insights/page.tsx`, `frontend/app/dashboard/metrics/page.tsx`, `frontend/components/onboarding/steps/PreviewTwinStep.tsx`.

Dependencies: none.

Risks: incorrect headers on public endpoints if applied broadly.

Acceptance checks: owner-only calls return 200 with bearer; no 401s due to missing auth; public calls still work without auth.

5. Consolidate ingestion pipelines

Scope: choose a single ingestion router for core paths and remove duplicate `/ingest/youtube` handling. Gate enhanced ingestion behind a feature flag if kept.

Files impacted: `backend/routers/ingestion.py`, `backend/routers/enhanced_ingestion.py`, `backend/main.py`.

Dependencies: product decision on enhanced ingestion availability.

Risks: breaking any internal usage of enhanced ingestion.

Acceptance checks: `/ingest/youtube|podcast|x|url|file` all route to a single implementation and produce consistent `source` status.

6. Consolidate retrieval path contracts

Scope: align `/chat`, `/chat-widget`, and `/public/chat` responses (stream vs non-stream) and unify API key transport method.

Files impacted: `backend/routers/chat.py`, `frontend/public/widget.js`, `frontend/app/share/[twin_id]/[token]/page.tsx`.

Dependencies: decision on streaming vs non-streaming for public share.

Risks: breaking public integrations.

Acceptance checks: public share chat and widget both return coherent responses using a documented schema; no parsing errors.

7. Disable non-critical modules touching critical path

Scope: feature-flag actions, governance, metrics, audio, interviews, debug retrieval if they interfere with core paths.

Files impacted: `backend/main.py`, feature flag config, `frontend` routes for those modules.

Dependencies: availability of feature flag system or environment variables.

Risks: user-visible feature removal.

Acceptance checks: core flows (twin create, ingestion, public chat) still work; non-critical routes are gated or hidden.
