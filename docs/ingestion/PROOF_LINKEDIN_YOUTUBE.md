# LinkedIn + YouTube Ingestion Proof

## Scope
- Repo: `d:\verified-digital-twin-brains`
- Required URLs:
- YouTube: `https://www.youtube.com/watch?v=HiC1J8a9V1I`
- LinkedIn: `https://www.linkedin.com/in/sainathsetti/`

## Validation Commands And Results
1. Backend full suite:
```powershell
cd backend
pytest -q
```
Result: `209 passed, 17 skipped`.

2. Frontend typecheck:
```powershell
cd frontend
cmd /c npm run typecheck
```
Result: pass (`tsc --noEmit`).

3. Frontend Playwright:
```powershell
cd frontend
cmd /c npx playwright test
```
Result: `6 passed, 8 skipped` (suite green).

## Proof Execution (Real DB/Pinecone)
1. Seed required URLs into the real ingestion pipeline:
```powershell
cd backend
python scripts/seed_linkedin_youtube_ingestion.py
```
Observed output:
- Twin created: `5698a809-87a5-4169-ab9b-c4a6222ae2dd`
- YouTube source: `140f782b-94a5-4b6f-910f-7ff98aa04bb3`, `status=completed`, `chunk_count=68`
- LinkedIn source: `e5d2a34e-fa5a-46e3-8e2c-1667ea5f5213`, `status=error`
- LinkedIn error: `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH` (expected compliance behavior)

2. Query proof from Supabase + Pinecone:
```powershell
cd backend
python scripts/prove_linkedin_youtube.py
```
Artifact written:
- `docs/ingestion/proof_outputs/proof_linkedin_youtube_20260208T095408Z.json`

## Supabase Evidence (from artifact)
- YouTube source row:
- `id=140f782b-94a5-4b6f-910f-7ff98aa04bb3`
- `status=live`
- `chunk_count=68`
- `last_provider=youtube`
- `last_step=live`
- `last_error=null`

- LinkedIn source row:
- `id=e5d2a34e-fa5a-46e3-8e2c-1667ea5f5213`
- `status=error`
- `last_provider=linkedin`
- `last_step=fetching`
- `last_error.code=LINKEDIN_BLOCKED_OR_REQUIRES_AUTH`
- `last_error.http_status=999`
- `last_error.retryable=false`

## Pinecone Evidence (from artifact)
- YouTube:
- `namespace_vector_count=68`
- `matches_for_source_count=3`
- `matches_for_source[].source_id` all equal `140f782b-94a5-4b6f-910f-7ff98aa04bb3`

- LinkedIn:
- `matches_for_source_count=0`
- This is correct for blocked LinkedIn URL ingestion (no profile text indexed).

## Compliance Confirmation (LinkedIn)
- No login automation/cookie theft/captcha bypass implemented.
- Behavior for `linkedin.com/in/...`:
- Attempt public OpenGraph fetch.
- On login wall/block, return terminal error `LINKEDIN_BLOCKED_OR_REQUIRES_AUTH`.
- UI guidance instructs owner to upload LinkedIn PDF export or paste profile text.

## UI Verification Steps (Production)
1. Open `Training Module -> Step 3 (Knowledge)`.
2. Add YouTube URL (`HiC1J8a9V1I`), wait for terminal state, open `Diagnostics`.
3. Confirm source row shows provider/step/status and diagnostics JSON.
4. Add LinkedIn URL (`/in/sainathsetti/`), confirm explicit blocked error.
5. Click `Retry` and verify new diagnostics events append in timeline.
6. For LinkedIn full content, upload a text-selectable PDF or paste profile text.

## SQL Queries (manual verification)
```sql
select id, twin_id, status, citation_url, chunk_count, last_provider, last_step, last_error, created_at
from sources
where id in (
  '140f782b-94a5-4b6f-910f-7ff98aa04bb3',
  'e5d2a34e-fa5a-46e3-8e2c-1667ea5f5213'
);
```

```sql
select source_id, count(*) as chunk_rows
from chunks
where source_id in (
  '140f782b-94a5-4b6f-910f-7ff98aa04bb3',
  'e5d2a34e-fa5a-46e3-8e2c-1667ea5f5213'
)
group by source_id;
```
