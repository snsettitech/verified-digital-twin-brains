# CDR-001: Canonical Contracts for Critical Path

Date: 2026-02-04
Status: Accepted (Phase 1)
Owner: Principal Engineer, Digital Brains

**Context**

The critical path must be production-grade and minimal. Current FE/BE drift and duplicate routes risk ingestion and public retrieval reliability. This decision record fixes the canonical contracts for Phase 1. These decisions are immutable for this phase.

**Decisions**

1) Ingestion is twin-scoped only

Canonical endpoints:
- `POST /ingest/file/{twin_id}`
- `POST /ingest/url/{twin_id}`
- `POST /ingest/youtube/{twin_id}`
- `POST /ingest/podcast/{twin_id}`
- `POST /ingest/x/{twin_id}`

No twin-less ingestion routes will be added for onboarding. Any existing twin-less usage must be updated or shims must forward to canonical routes with deprecation logs.

2) API keys: canonical is tenant router `/api-keys`

Canonical CRUD endpoints:
- `GET /api-keys`
- `POST /api-keys`
- `DELETE /api-keys/{key_id}`

Any duplicate twin-key router endpoints (also on `/api-keys` in `backend/routers/auth.py`) are non-canonical for this phase.

3) Streaming chat schema canon (all streaming endpoints)

Canonical NDJSON schema (one JSON object per line) for `/chat/{twin_id}` and `/chat-widget/{twin_id}`:
- `type: "metadata" | "content" | "clarify" | "done" | "error"`
- `content` event uses field `token` (not `content` or `answer_token`)

Canonical request schema:
- `{ query: string, conversation_id?: string, group_id?: string, metadata?: object, mode?: "owner"|"public" }`

Compatibility tolerance (one release window):
- accept `{ message }` and map to `query` server-side

4) Training jobs observability is in-scope

Canonical endpoints:
- `GET /training-jobs?twin_id=...`
- `POST /training-jobs/{job_id}/retry`

These must be tenant- and twin-scoped correctly and used by the UI without 404s.

5) Known tolerance contracts during migration

- `/sources/{source_id}/reject` accepts query param `reason` OR JSON `{ reason }`.
- `/sources/bulk-approve` accepts raw `string[]` OR `{ source_ids: string[] }`.
- `/sources/{source_id}/health` response must include `checks: []` for FE compatibility. If no checks exist, return `checks: []` derived from `logs` or empty.

**Rationale**

These contracts minimize scope, preserve tenant and twin isolation, and allow minimal shims to eliminate current FE/BE drift without broad refactors.

**Consequences**

- Onboarding and public widget code must conform to canonical schema or use compatibility shims.
- Duplicate routes and non-canonical API keys should be flagged for removal in Phase 5 after proof packets pass.

**References**

- `CRITICAL_PATH_CONTRACT_MATRIX.md`
- `FE_BE_DRIFT_REPORT.md`
- `DUPLICATION_COMPLEXITY_REPORT.md`
- `SCOPE_CUT_PROPOSAL.md`
- `CRITICAL_PATH_EXECUTION_PLAN.md`