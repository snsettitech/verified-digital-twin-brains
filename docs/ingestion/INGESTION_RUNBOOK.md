# Ingestion Runbook

This runbook is for debugging URL/file ingestion failures end-to-end. It assumes the backend uses Supabase for persistence, Pinecone for vectors, and `training_jobs` for async work.

## Quick Triage

1. Check backend health
- `GET /health`
- Look at `ingestion_diagnostics_schema.available`
  - `false`: apply `backend/database/migrations/20260207_ingestion_diagnostics.sql` in Supabase SQL editor, then redeploy/restart backend.

2. Check the Source row
- In UI: Dashboard -> Console -> Knowledge -> find the row -> `Diagnostics`
- In Supabase SQL editor:
```sql
select id, twin_id, status, health_status, filename, citation_url, chunk_count, extracted_text_length
from sources
where twin_id = '<TWIN_ID>'
order by created_at desc
limit 20;
```

If diagnostics migration is applied, also inspect:
```sql
select id, status, last_provider, last_step, last_error, last_error_at, last_event_at
from sources
where id = '<SOURCE_ID>';
```

3. Check ingestion logs (fallback and always useful)
```sql
select created_at, log_level, message, metadata
from ingestion_logs
where source_id = '<SOURCE_ID>'
order by created_at desc
limit 100;
```

4. Check training job state
```sql
select id, status, job_type, priority, error_message, metadata, created_at, started_at, completed_at
from training_jobs
where source_id = '<SOURCE_ID>'
order by created_at desc
limit 10;
```

If jobs are stuck at `queued`, the worker is not processing the queue (see "Worker Debug").

## Worker Debug

If the worker is running:
- It should continuously poll for jobs and mark them `processing` -> `complete` or `failed`.

Common failure modes:
- Redis is optional. If `REDIS_URL` is not set, the worker falls back to DB-backed polling (`training_jobs` + `jobs` tables).
  - If jobs are still stuck at `queued`, the worker likely lacks DB write permissions (missing `SUPABASE_SERVICE_KEY`) or is not running.
- Worker env missing keys used by ingestion/indexing (`OPENAI_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME`, Supabase service key).
- Pinecone index unreachable or wrong index name.

Manual fallback (owner-only API):
- Use `POST /training-jobs/process-queue?twin_id=<TWIN_ID>` to process queued `training_jobs` in-process for debugging.

## Retry / Replay

From UI:
- Knowledge table -> `Retry`

Via API:
```bash
curl -X POST "$BACKEND_URL/sources/<SOURCE_ID>/retry" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

If a specific training job failed:
```bash
curl -X POST "$BACKEND_URL/training-jobs/<JOB_ID>/retry" \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

## Common Error Codes And Fixes

### `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH`
Meaning:
- LinkedIn returned a login wall or bot-block (often HTTP 999). We do not bypass this.

Fix:
- Use the fallback: upload your LinkedIn profile PDF export or paste profile text (Knowledge -> Add Knowledge -> Paste text).

### `YOUTUBE_TRANSCRIPT_UNAVAILABLE`
Meaning:
- Captions/transcript not available, rate-limited, or extraction blocked.

Fix:
- Retry (might be transient).
- Provide `GOOGLE_API_KEY` (YouTube Data API validation) if available.
- If a video is age/region gated, configure `YOUTUBE_COOKIES_FILE` and/or `YOUTUBE_PROXY` for your deployment.
- If the video has no captions, pick a different video with CC enabled.

### `X_BLOCKED_OR_UNSUPPORTED`
Meaning:
- Public extraction strategies failed (X/Twitter frequently blocks server IPs).

Fix:
- Retry (some strategies are best-effort).
- Fallback: copy thread text and paste/upload as a text source.

### `FILE_EXTRACTION_EMPTY` / `FILE_EXTRACTION_FAILED`
Meaning:
- The file uploaded but no extractable text found (common for scanned PDFs).

Fix:
- Re-export as a text-based PDF.
- Upload a text/markdown export.

### `EMBEDDINGS_FAILED` / `INDEXING_FAILED`
Meaning:
- Embedding provider failed or Pinecone upsert failed.

Fix:
- Check `OPENAI_API_KEY` validity and quotas.
- Check Pinecone env vars and connectivity.
- Retry.

## DEV_MODE

If you need stacktraces persisted in diagnostics:
- Set `DEV_MODE=true`
- Re-run ingestion

Production should generally keep `DEV_MODE=false`.
