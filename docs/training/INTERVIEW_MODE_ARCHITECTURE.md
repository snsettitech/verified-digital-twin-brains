# Interview Mode Architecture

## Purpose
Step 2 interview mode captures owner voice/text signals and turns them into proposed owner memories for Inbox review.

## End-To-End Flow
1. Frontend starts session via `POST /api/interview/sessions`.
2. Backend builds `system_prompt` from:
- prior context (`Zep/Graphiti` via `get_user_context`)
- Step 1 intent profile (`settings.intent_profile`)
- Step 1 public intro (`settings.public_intro`)
3. Frontend requests ephemeral Realtime key via `POST /api/interview/realtime/sessions`.
4. Browser opens WebRTC to OpenAI Realtime and streams mic audio.
5. Hook appends transcript turns from:
- `conversation.item.input_audio_transcription.completed` (user)
- `response.audio_transcript.done` (assistant)
6. On stop, frontend calls `POST /api/interview/sessions/{session_id}/finalize`.
7. Backend extracts memories, proposes them to `owner_beliefs` as `status=proposed`, and records final session metadata.
8. Step 4 Inbox loads proposed memories from `GET /twins/{twin_id}/owner-memory?status=proposed`.

## Core Components
- Session API: `backend/routers/interview.py`
- Extraction pipeline: `backend/modules/memory_extractor.py`
- Owner memory persistence: `backend/modules/owner_memory_store.py`
- Realtime browser hook: `frontend/lib/hooks/useRealtimeInterview.ts`
- Step 2 + Step 4 UI: `frontend/components/console/tabs/TrainingTab.tsx`

## Memory Extraction Pipeline
1. Transcript normalization:
- drops filler-only turns
- coalesces fragmented same-role turns
- now also drops short assistant ack-only turns (`Got it`, `Understood`) to preserve owner thought continuity
2. LLM extraction:
- requests strict JSON object with top-level `memories` array
- accepts multiple response shapes defensively
3. Heuristic fallback:
- if LLM fails/malformed/empty, extracts `goal|preference|constraint|boundary|intent` with regex rules
4. Finalize filter:
- confidence `< 0.6` is skipped
- accepted memories map to owner memory types and are inserted as `status=proposed`

## Why Step 2 Previously Looked Like No-Op
1. Realtime transcript fragmentation produced many tiny turns.
2. Extractor had narrow JSON assumptions and weak fallback behavior.
3. In some runs, no memory crossed confidence threshold, so Inbox remained empty.
4. Frontend reused old transcript buffer across interview runs, which polluted the next finalize request.

## Fixes Applied
- Extraction now tolerates shape drift and has deterministic fallback.
- Transcript normalization now bridges owner statements split by trivial assistant acknowledgements.
- New interview starts with a fresh transcript buffer.
- Finalize response exposes `proposed_count`, `proposed_failed_count`, and `notes` so UI can show concrete outcome.

## Persistence And Observability
- `interview_sessions` stores transcript and finalize metadata.
- `owner_beliefs` stores proposed memories for owner review.
- `source_events`/`sources.last_error` handle ingestion diagnostics (separate from interview flow).

## Debug Checklist
1. Verify `finalize` response includes non-zero `proposed_count`.
2. Query `owner_beliefs` for `status='proposed'` and `provenance.source_type='interview'`.
3. Check Step 4 API calls in browser network tab:
- `/twins/{twin_id}/owner-memory?status=proposed`
4. If zero proposals, inspect finalize `notes` for:
- low confidence skip
- schema/status insert failures
