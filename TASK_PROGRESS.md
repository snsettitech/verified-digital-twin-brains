# Training + Ingestion Incident: Root Causes, Tasks, Status

## Reported Production Issues
1. One owner saw multiple twins (`4 twins`) even though onboarding was incomplete.
2. Onboarding FAQ step intermittently crashed (`reading 'question'` on undefined FAQ slot).
3. Interview Step 2 felt like a no-op (`No memories were extracted from transcript`).
4. Step 4 Inbox stayed empty because interview proposals were not created.
5. Knowledge diagnostics endpoints returned `404` for `/sources/{source_id}/events` and `/logs`.
6. YouTube and LinkedIn diagnostics were partially visible, but timeline/log endpoints failed.
7. LinkedIn URL ingestion was blocked (expected), but proof pipeline had gaps.

## Root-Cause Chain
### Architecture
- Read path `/auth/my-twins` previously swallowed tenant resolution failures and returned `[]`.
- `POST /twins` had no server-side idempotency protection for retry races.
- Route precedence in `sources` shadowed diagnostics endpoints.

### Backend correctness
- Memory extraction expected narrow response shapes and often degraded to empty output.
- Realtime interview transcripts were fragmented by short assistant acks; extraction quality dropped.
- Proof script queried a non-existent column (`sources.updated_at`) and gave false-negative proof.

### Product/UX
- Interview completion did not always yield visible proposed memories, reducing owner trust.
- Starting a new interview reused prior transcript buffer and polluted next finalize payload.

## Fix Plan And Status
### Task A: Harden twin listing and onboarding safety
- A1. Make `/auth/my-twins` fail loudly on tenant resolution errors (`503`), not empty list.
- A2. Add onboarding client idempotency + sync-first behavior.
- A3. Add server-side create-twin idempotency for duplicate name/race retries.
- Status: `DONE`

### Task B: Fix interview memory extraction reliability
- B1. Support multiple model JSON shapes.
- B2. Add deterministic heuristic fallback.
- B3. Coalesce fragmented user turns across trivial assistant acknowledgements.
- B4. Reset transcript buffer at interview start.
- Status: `DONE`

### Task C: Restore diagnostics endpoints
- C1. Reorder sources routes so `/sources/{source_id}/events|logs` are never shadowed.
- C2. Add route precedence regression tests.
- Status: `DONE`

### Task D: Strengthen proof pipeline
- D1. Fix proof script schema assumptions (`updated_at` bug).
- D2. Add ingestion seed script for required LinkedIn/YouTube proof runs.
- D3. Filter Pinecone evidence by expected `source_id`.
- Status: `DONE`

## New Regression Tests Added
- `backend/tests/test_auth_my_twins.py`
- `backend/tests/test_sources_route_precedence.py`
- `backend/tests/test_twins_create_idempotency.py`
- `backend/tests/test_memory_extractor.py` (robustness cases expanded)

## Current Validation Status
- Backend: `pytest -q` -> `209 passed, 17 skipped`
- Frontend typecheck: `cmd /c npm run typecheck` -> pass
- Playwright: `cmd /c npx playwright test` -> `6 passed, 8 skipped`

## Proof Artifacts
- `docs/ingestion/PROOF_LINKEDIN_YOUTUBE.md`
- `docs/ingestion/proof_outputs/proof_linkedin_youtube_20260208T095408Z.json`

## Remaining Operational Actions
1. Keep `20260207_ingestion_diagnostics.sql` applied in target environment.
2. Ensure worker process remains healthy for queued training jobs.
3. For blocked LinkedIn URLs, use PDF/text fallback path for full profile ingestion.
