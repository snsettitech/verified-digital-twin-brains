# Training + Ingestion Incident: Root-Cause Backlog and Fix Plan

## 1) Reported Issues (from production UI)

1. Onboarding FAQ step crashes with `Cannot read properties of undefined (reading 'question')`.
2. Existing twin disappeared after refresh; `/auth/my-twins` returned `0 twins`.
3. Interview felt like a no-op: unclear if Step 2 actually persisted memories.
4. Step 4 Inbox often empty after interview.
5. YouTube ingestion failed with auth wall but error was marked retryable.
6. LinkedIn URL returned blocked error; diagnostics timeline showed no step events.
7. LinkedIn PDF upload returned `FILE_EXTRACTION_EMPTY`.

## 2) Root-Cause Chain (multi-perspective)

### Architect view
- Read-path tenant resolution had side effects: `resolve_tenant_id()` could create/re-link tenants during `/auth/my-twins` reads, which risks tenant drift and "missing twins".
- Interview finalization returned only `write_count` (Zep writes), not proposal outcomes; UI lacked clear contract for "extracted vs proposed vs failed".
- Diagnostics timeline depends on migration `20260207_ingestion_diagnostics.sql`; when missing in production DB, event timeline cannot render.

### Senior Engineer view
- FAQ crash: sparse FAQ array entries reached `saveFaqs()` and were dereferenced without guards.
- YouTube retryability: `YOUTUBE_TRANSCRIPT_UNAVAILABLE` was treated retryable by default even when underlying provider error was `auth`.
- YouTube retry loop had double attempt accounting (`strategy.attempts += 1` + `log_attempt()` increment), distorting retry telemetry.

### Product Manager view
- User receives "Interview saved" but not "what exactly got stored", causing trust gap.
- LinkedIn blocked behavior is compliant, but fallback path needs clearer expectations: URL metadata only vs full profile via text-selectable export.
- Missing migration produces partial diagnostics UX, perceived as broken flow.

### Owner/User view
- "I spoke a lot, but I cannot see what got captured."
- "I lost my twin and got pushed back to onboarding."
- "I cannot complete onboarding due FAQ crash."
- "I see errors but not actionable context unless diagnostics schema exists."

## 3) Fix Tasks and Subtasks

### Task A: Stop onboarding FAQ crash
- A1. Ensure FAQ state never produces sparse entries.
- A2. Guard FAQ persistence loop against undefined entries.
- A3. Validate via frontend typecheck.
- Status: `DONE`

### Task B: Prevent read-path tenant drift (lost twin)
- B1. Make tenant lookup non-mutating on lookup failure.
- B2. Add `create_if_missing` control to `resolve_tenant_id`.
- B3. Use `create_if_missing=False` for `/auth/my-twins` and `/auth/whoami`.
- B4. Add unit tests proving no tenant creation in read-only mode.
- Status: `DONE`

### Task C: Make interview persistence observable
- C1. Add `proposed_count`, `proposed_failed_count`, `notes` to finalize response.
- C2. Persist proposal diagnostics into interview session metadata.
- C3. Update Step 2 UI toast to reflect proposals vs extraction outcome.
- C4. Add unit test for proposal-failure diagnostics.
- Status: `DONE`

### Task D: Correct YouTube retry diagnostics semantics
- D1. Map provider-specific category (`auth/network/...`) into diagnostics error object.
- D2. Classify `YOUTUBE_TRANSCRIPT_UNAVAILABLE` retryability by provider error category.
- D3. Fix retry attempt accounting bug in ingestion loop.
- D4. Add unit tests for retryability classification.
- Status: `DONE`

### Task E: Validate full test surface
- E1. Run targeted backend tests for new logic.
- E2. Run full backend `pytest`.
- E3. Run frontend `typecheck`.
- E4. Run ingestion diagnostics Playwright spec.
- Status: `DONE`

### Task F: Harden PDF extraction path
- F1. Make PDF extraction tolerant of pages returning `None` from `extract_text()`.
- F2. Add regression test for mixed `None` + text pages.
- Status: `DONE`

## 4) Remaining Production Actions (non-code)

1. Apply `backend/database/migrations/20260207_ingestion_diagnostics.sql` in production Supabase.
2. Confirm worker process is running and consuming queued ingestion jobs in production.
3. For LinkedIn profile content:
   - URL ingestion: only OpenGraph metadata when public.
   - Full profile ingestion: upload text-selectable PDF export or paste text.
4. For YouTube auth/age-gated videos: expect terminal auth error unless allowed caption/audio retrieval is possible.

## 5) Verification Evidence (local)

- Backend tests: `217 passed, 17 skipped`.
- Frontend typecheck: `tsc --noEmit` passed.
- Playwright e2e: `tests/e2e/ingestion_diagnostics.spec.ts` passed.
