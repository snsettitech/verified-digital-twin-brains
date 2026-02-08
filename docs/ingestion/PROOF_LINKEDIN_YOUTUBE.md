# LinkedIn + YouTube Ingestion Proof

## Scope
- Repository: `d:\verified-digital-twin-brains`
- Required URLs:
  - YouTube: `https://www.youtube.com/watch?v=HiC1J8a9V1I`
  - LinkedIn: `https://www.linkedin.com/in/sainathsetti/`

## What Was Implemented
- Unified diagnostics schema + runbook already added:
  - `docs/ingestion/INGESTION_DIAGNOSTICS_SPEC.md`
  - `docs/ingestion/INGESTION_RUNBOOK.md`
- YouTube transcript compatibility hardening:
  - Added `fetch_youtube_transcript_compat(...)` in `backend/modules/ingestion.py` to support both old and new `youtube-transcript-api` method shapes (`fetch/list` and `get_transcript/list_transcripts`).
- Regression tests for transcript API compatibility:
  - `backend/tests/test_youtube_transcript_api_compat.py`
- Proof automation script added:
  - `backend/scripts/prove_linkedin_youtube.py`
  - Writes JSON artifact to `docs/ingestion/proof_outputs/`.

## Commands Run And Results

1. Regression + diagnostics tests:
```powershell
cd backend
python -m pytest tests/test_youtube_transcript_api_compat.py tests/test_ingestion_diagnostics_contract.py tests/test_media_integration.py -q
```
Result: `8 passed`.

2. Full backend test sweep:
```powershell
cd backend
python -m pytest -q
```
Result: `194 passed, 18 skipped`.

3. Frontend typecheck:
```powershell
cd frontend
npm run typecheck
```
Result: pass (`tsc --noEmit` completed with no errors).

4. Frontend Playwright:
```powershell
cd frontend
npx playwright test
```
Result: failed in this environment with `spawn EPERM` (process execution permission issue).  
Note: `npx playwright test --list` succeeds and lists all tests.

5. LinkedIn + YouTube proof script:
```powershell
cd backend
python scripts/prove_linkedin_youtube.py
```
Result:
- Script executed and wrote:
  - `docs/ingestion/proof_outputs/proof_linkedin_youtube_20260208T042258Z.json`
- Current environment could not connect to Supabase endpoint:
  - `[WinError 10061] No connection could be made because the target machine actively refused it`
- Therefore no live DB/Pinecone rows were retrievable from this run.

## Proof Artifact Snapshot
File: `docs/ingestion/proof_outputs/proof_linkedin_youtube_20260208T042258Z.json`

Key fields:
- `sources.youtube = null`
- `sources.linkedin = null`
- `errors` contains Supabase connection refusal for both lookups.

## Compliance Behavior (LinkedIn)
- LinkedIn ingestion path is compliance-first (no login automation/scraping bypass):
  - Implemented in `backend/modules/ingestion.py` (`ingest_linkedin_open_graph`).
- Behavior:
  - Attempt public OG metadata fetch.
  - If blocked/login wall, return terminal error:
    - `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH`
  - UI/operator fallback: upload LinkedIn PDF export or paste profile text.

## UI Verification Steps (Production)
1. Open Training -> Knowledge step.
2. Submit YouTube URL and observe status transitions (`queued -> fetching -> parsed -> chunked -> embedded -> indexed/live`) or explicit terminal error.
3. Open Diagnostics on the source row and verify:
   - provider
   - step timeline
   - error object (`code`, `message`, `http_status`, `retryable`, `raw`).
4. Submit LinkedIn URL and verify either:
   - OG metadata ingested and indexed, or
   - explicit blocked error with fallback instruction.
5. Use `Retry` on failed rows and verify diagnostics timeline appends new events.

## SQL Queries To Capture DB Proof
Run in Supabase SQL editor:

```sql
select id, twin_id, status, citation_url, chunk_count, last_provider, last_step, last_error, created_at
from sources
where citation_url in (
  'https://www.youtube.com/watch?v=HiC1J8a9V1I',
  'https://www.linkedin.com/in/sainathsetti/'
)
order by created_at desc;
```

```sql
select source_id, count(*) as chunk_rows
from chunks
where source_id in (
  select id from sources
  where citation_url in (
    'https://www.youtube.com/watch?v=HiC1J8a9V1I',
    'https://www.linkedin.com/in/sainathsetti/'
  )
)
group by source_id;
```

## Pinecone Verification Command
```powershell
cd backend
python scripts/prove_linkedin_youtube.py
```
Expected when connectivity is available:
- `namespace_vector_count > 0` for relevant `twin_id`
- non-empty `matches` with metadata including `source_id` / `filename`.

