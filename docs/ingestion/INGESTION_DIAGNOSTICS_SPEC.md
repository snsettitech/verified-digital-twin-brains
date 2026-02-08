# Ingestion Diagnostics Spec

## Goals
- Every ingestion produces observable progress (not silent/no-op).
- Every failure produces a persisted, actionable error object.
- UI shows per-source status, last step, last error, and supports Retry + View diagnostics.
- Must not break: onboarding, training, share chat, SSE streaming, auth, tenant isolation.

## Non-goals
- ToS-violating provider integrations (notably LinkedIn).
- A brand new queueing system (reuse existing `training_jobs` + `jobs` + worker). Redis is optional; when missing, the worker dequeues from Supabase tables.

## Canonical Ingestion State Machine

### High-level source status (backward compatible)
We keep `sources.status` compatible with existing flows:
- `pending`: queued, not started yet
- `processing`: in progress (any step)
- `live`: indexed and available for retrieval
- `error`: terminal failure (requires user action or retry)

### Fine-grained steps (diagnostics timeline)
Stored in `sources.last_step` and the `source_events` timeline:
1. `queued`
2. `fetching`
3. `parsed`
4. `chunked`
5. `embedded`
6. `indexed`
7. `live` (terminal success)
8. `error` (terminal failure; status is still `error` but `last_step` should remain the step that failed)

Notes:
- Steps are provider-agnostic; providers may skip steps.
- `sources.status` is derived; steps/timeline are the truth for debugging.

## Providers
Stored in `sources.last_provider` and `source_events.provider`:
- `youtube`
- `x`
- `linkedin`
- `web`
- `podcast`
- `file`

Provider detection rules:
- YouTube: `youtube.com`, `youtu.be`
- X: `x.com`, `twitter.com`
- LinkedIn: `linkedin.com/...`
- Podcast: `.rss` or known feed patterns
- Otherwise: `web`

## Error Schema (persisted as JSON)
Persisted to `sources.last_error` (JSONB) and copied to the failing `source_events.error`.

```json
{
  "code": "YOUTUBE_TRANSCRIPT_UNAVAILABLE",
  "message": "No transcript could be extracted. This video may not have captions.",
  "provider": "youtube",
  "step": "fetching",
  "http_status": 403,
  "provider_error_code": "quotaExceeded",
  "retryable": false,
  "correlation_id": "req_abc123",
  "raw": {
    "url": "https://www.youtube.com/watch?v=...",
    "response_snippet": "<html>...</html>"
  },
  "stacktrace": null
}
```

Field requirements:
- `code`: stable string code (UI uses for help text).
- `message`: user-facing, actionable explanation.
- `provider`: one of the known providers.
- `step`: one of the steps above.
- `http_status`: when an HTTP call failed.
- `provider_error_code`: raw provider error code if available.
- `retryable`: UI uses this to enable/disable Retry.
- `correlation_id`: propagated from `x-correlation-id`/`x-request-id` when available.
- `raw`: sanitized debug payload (never include secrets, cookies, Authorization).
- `stacktrace`: only when `DEV_MODE=true`.

## Database Persistence

### Required migration
Apply `backend/database/migrations/20260207_ingestion_diagnostics.sql` in the Supabase SQL editor.

Without this migration:
- ingestion still works, but step timeline and `last_error` fields are not persisted
- the backend falls back to `ingestion_logs` for diagnostics
- `GET /sources/{source_id}/events` returns `503` with an actionable message
- `/health` reports `ingestion_diagnostics_schema.available=false`

### `sources` table additions
Required columns:
- `last_provider text`
- `last_step text`
- `last_error jsonb`
- `last_error_at timestamptz`
- `last_event_at timestamptz`

### `source_events` table
Append-only (rows created at step start and updated at completion/error).

Required columns:
- `id uuid pk`
- `source_id uuid fk -> sources.id`
- `twin_id uuid fk -> twins.id`
- `provider text`
- `step text`
- `status text` (`started` | `completed` | `error`)
- `message text null`
- `metadata jsonb default {}`
- `error jsonb null`
- `correlation_id text null`
- `started_at timestamptz`
- `ended_at timestamptz null`
- `created_at timestamptz default now()`

Indexes:
- `(source_id, created_at)`
- `(twin_id, created_at)`

Security:
- `source_events` must have RLS enabled and a tenant-isolated select policy (migration includes this).

## Backend API Contract

### Existing endpoints (kept)
- `POST /ingest/url/{twin_id}`
- `POST /ingest/youtube/{twin_id}`
- `POST /ingest/x/{twin_id}`
- `POST /ingest/podcast/{twin_id}`
- `POST /ingest/file/{twin_id}`
- `GET /sources/{twin_id}`
- `GET /sources/{source_id}/logs` (legacy `ingestion_logs`)

### New endpoints
- `GET /sources/{source_id}/events`
  - returns chronological step timeline (or `503` if schema missing)
- `POST /sources/{source_id}/retry`
  - re-queues ingestion using `sources.citation_url` when present
  - clears `sources.last_error` when diagnostics schema exists

### Ingestion endpoint behavior
- URL-based ingests must:
  - create a `sources` row immediately (`status=pending`)
  - set `citation_url`
  - enqueue a `training_jobs` record
  - return quickly with `{ source_id, job_id, status }`
- File uploads:
  - create `sources` row immediately
  - extract text quickly
  - enqueue indexing work

## Frontend UI Requirements (Knowledge Table)

### Content table columns
- Source (filename; link out when `citation_url` exists)
- Provider
- Status pill (`pending` | `processing` | `live` | `error`)
- Last step (`fetching`, `chunked`, etc.)
- Last updated (`sources.last_event_at` preferred)
- Actions:
  - `Diagnostics` opens drawer/modal with timeline + logs + last_error
  - `Retry` calls backend retry

### Polling behavior
After submitting an ingest:
- poll `GET /sources/{twin_id}` every 2s for up to 90s, or until no sources are `pending`/`processing`
- if timeout: show "still processing" guidance and keep row visible with its latest status

## Compliance: LinkedIn
LinkedIn ingestion is compliance-first:
- do not implement headless login, cookie theft, captcha bypass, or any ToS-violating automation
- attempt a public OpenGraph fetch (`og:title`, `og:description`, `og:image`, canonical URL)
- if blocked (login wall, redirects, HTTP 999, missing useful OG):
  - persist terminal error `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH`
  - UI instructs: upload LinkedIn profile PDF export or paste profile text for full ingestion
