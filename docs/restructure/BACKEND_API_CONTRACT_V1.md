# Backend API Contract V1 (Plan Only)

## Contract Principles
- Keep existing paths where possible to minimize frontend changes.
- Consolidate to a single API key model and a single jobs model.
- Web-only chat and embed only (no Telegram, no voice, no actions).
- All endpoints require tenant-scoped auth unless marked public.

## Authentication And Tenant Scope
- JWT auth and tenant scoping implemented in `backend/modules/auth_guard.py`.
- Auth routes live in `backend/routers/auth.py` and are registered in `backend/main.py`.

## SSE Event Schema (Chat)
- Implemented in `backend/routers/chat.py`.
- SSE events are JSON lines with `type` values:
  - `metadata`: includes `conversation_id`, `citations`, `confidence_score`, `owner_memory_refs`, `owner_memory_topics`.
  - `content`: includes `content` (full text chunk).
  - `done`: indicates end of stream.
  - `clarify`: emitted when identity gate needs owner confirmation.
  - `error`: emitted on exception.

## Canonical Endpoints By Module

### Auth / Users / Tenant
- `POST /auth/sync-user` (keep). Implemented in `backend/routers/auth.py`.
- `GET /auth/me` (keep). `backend/routers/auth.py`.
- `GET /auth/whoami` (keep). `backend/routers/auth.py`.
- `GET /auth/my-twins` (keep). `backend/routers/auth.py`.
- `GET /users` (keep). `backend/routers/auth.py` -> `modules/user_management.py`.
- `POST /users/invite` (keep). `backend/routers/auth.py` -> `modules/user_management.py`.
- `GET /auth/invitation/{token}` (ADD). Use `modules/user_management.validate_invitation_token` in `backend/modules/user_management.py`.
- `POST /auth/accept-invitation` (ADD). Use `modules/user_management.accept_invitation` in `backend/modules/user_management.py`.

### Twins (Experts)
- `POST /twins` (keep). Implemented in `backend/routers/twins.py`.
- `GET /twins` (keep). `backend/routers/twins.py`.
- `GET /twins/{twin_id}` (keep). `backend/routers/twins.py`.
- `PATCH /twins/{twin_id}` (keep; restrict to settings needed). `backend/routers/twins.py` and `backend/modules/schemas.py: TwinSettingsUpdate`.
- `POST /twins/{twin_id}/archive` and `DELETE /twins/{twin_id}` (keep). `backend/routers/twins.py`.

### Studio Build: Ingestion + Sources
- Ingestion is **auto-indexed**. There is no manual source approval workflow or `auto_index` flag.
- `POST /ingest/file/{twin_id}` (keep). `backend/routers/ingestion.py` uses `backend/modules/ingestion.py`.
- `POST /ingest/url/{twin_id}` (keep). `backend/routers/ingestion.py`.
- `POST /ingest/youtube/{twin_id}` (keep if media ingestion remains). `backend/routers/ingestion.py` -> `backend/modules/media_ingestion.py`.
- `POST /ingest/podcast/{twin_id}` (keep if media ingestion remains). `backend/routers/ingestion.py`.
- `POST /ingest/x/{twin_id}` (optional; decide to keep or remove). `backend/routers/ingestion.py`.
- `GET /sources/{twin_id}` (keep). `backend/routers/sources.py`.
- `DELETE /sources/{twin_id}/{source_id}` (keep). `backend/routers/sources.py`.
- `GET /sources/{source_id}/logs` (keep). `backend/routers/sources.py` -> `ingestion_logs` table in `backend/database/migrations/migration_phase6_mind_ops.sql`.
- `POST /sources/{source_id}/re-extract` (keep). `backend/routers/sources.py`.

### Studio Build: Knowledge Quality And Verified QnA
- `GET /twins/{twin_id}/knowledge-profile` (keep). `backend/routers/knowledge.py` -> `backend/modules/observability.get_knowledge_profile`.
- `GET /twins/{twin_id}/verified-qna` (keep). `backend/routers/knowledge.py`.
- `POST /twins/{twin_id}/verified-qna` (ADD). Use `backend/modules/verified_qna.create_verified_qna` without escalation dependency.
- `GET /verified-qna/{qna_id}` (keep). `backend/routers/knowledge.py`.
- `PATCH /verified-qna/{qna_id}` (keep). `backend/routers/knowledge.py`.
- `DELETE /verified-qna/{qna_id}` (keep). `backend/routers/knowledge.py`.

### Studio Build: Roles And Boundaries
- `GET /twins/{twin_id}/access-groups` (keep). `backend/routers/twins.py`.
- `POST /twins/{twin_id}/access-groups` (keep). `backend/routers/twins.py`.
- `GET /access-groups/{group_id}` (keep). `backend/routers/twins.py`.
- `PATCH /access-groups/{group_id}` (keep). `backend/routers/twins.py`.
- `DELETE /access-groups/{group_id}` (keep). `backend/routers/twins.py`.
- `GET /access-groups/{group_id}/members` (keep). `backend/routers/twins.py`.
- `POST /twins/{twin_id}/group-memberships` (keep). `backend/routers/twins.py`.
- `DELETE /group-memberships/{membership_id}` (keep). `backend/routers/twins.py`.
- `POST /access-groups/{group_id}/permissions` (keep). `backend/routers/twins.py`.
- `DELETE /access-groups/{group_id}/permissions/{content_type}/{content_id}` (keep). `backend/routers/twins.py`.
- `GET /access-groups/{group_id}/permissions` (keep). `backend/routers/twins.py`.

### Owner Memory + Clarifications (Identity Gate)
- `GET /twins/{twin_id}/owner-memory` (keep). `backend/routers/owner_memory.py`.
- `DELETE /twins/{twin_id}/owner-memory/{memory_id}` (keep). `backend/routers/owner_memory.py`.
- `GET /twins/{twin_id}/clarifications` (keep). `backend/routers/owner_memory.py`.
- `POST /twins/{twin_id}/clarifications/{clarification_id}/resolve` (keep). `backend/routers/owner_memory.py`.

### Launch: Share Links + Embed
- `GET /twins/{twin_id}/share-link` (keep). `backend/routers/auth.py` -> `backend/modules/share_links.py`.
- `POST /twins/{twin_id}/share-link` (keep). `backend/routers/auth.py` -> `backend/modules/share_links.py`.
- `PATCH /twins/{twin_id}/sharing` (keep). `backend/routers/auth.py`.
- `GET /public/validate-share/{twin_id}/{token}` (keep, public). `backend/routers/auth.py`.
- `POST /public/chat/{twin_id}/{token}` (keep, public JSON response). `backend/routers/chat.py`.
- `POST /chat-widget/{twin_id}` (keep, public SSE). `backend/routers/chat.py`.

### API Keys (Canonical)
- Use tenant-scoped API keys from `backend/routers/api_keys.py` + `backend/database/migrations/migration_scope_enforcement.sql`.
- Deprecate twin-scoped keys in `backend/modules/api_keys.py` and `/api-keys` routes in `backend/routers/auth.py`.
- Ensure `POST /chat-widget/{twin_id}` accepts tenant keys with `allowed_twin_ids` or `scopes`.

### Operate: Conversations + Audience + Analytics
- `GET /conversations/{twin_id}` (keep). `backend/routers/chat.py`.
- `GET /conversations/{conversation_id}/messages` (keep). `backend/routers/chat.py`.
- `GET /metrics/dashboard/{twin_id}` (keep). `backend/routers/metrics.py`.
- `GET /metrics/top-questions/{twin_id}` (keep). `backend/routers/metrics.py`.
- `GET /metrics/daily/{twin_id}` (keep). `backend/routers/metrics.py`.
- `GET /metrics/activity/{twin_id}` (keep). `backend/routers/metrics.py`.
- `GET /metrics/usage/{twin_id}` (keep). `backend/routers/metrics.py`.
- Audience list (ADD): a `GET /audience/{twin_id}` endpoint that summarizes unique visitors from `sessions` and `conversations` tables (data in `backend/database/migrations/migration_phase7_omnichannel.sql`).

### Enterprise Basics
- `GET /governance/audit-logs` (keep). `backend/routers/governance.py`.
- `GET /metrics/health` (keep). `backend/routers/metrics.py`.
- `GET /observability/health` (keep). `backend/routers/observability.py`.

## Explicit Removals From V1
- Actions engine endpoints (`backend/routers/actions.py`).
- Escalations endpoints (`backend/routers/escalations.py`).
- Cognitive, interview, reasoning, audio endpoints (`backend/routers/cognitive.py`, `backend/routers/interview.py`, `backend/routers/reasoning.py`, `backend/routers/audio.py`).
- Enhanced ingestion endpoints (`backend/routers/enhanced_ingestion.py`).
- Specializations + VC endpoints (`backend/routers/specializations.py`, `backend/api/vc_routes.py`).

## Compatibility Strategy
- Keep old paths for one release window where frontend already calls them.
- Add new endpoints (invitation accept, verified QnA create, audience list) in-place without breaking existing flows.
