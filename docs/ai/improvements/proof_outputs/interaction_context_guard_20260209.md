# Interaction Context Guard Proof (2026-02-09)

## Scope
This proof covers the completed "next step" after training sessions:
- strict server-side context guard that forces a new conversation when interaction context changes
- UI wiring to accept server-rotated conversation IDs
- migration + RLS for training sessions and interaction context metadata

## Code Deliverables
- `backend/modules/interaction_context.py`
- `backend/modules/training_sessions.py`
- `backend/routers/training_sessions.py`
- `backend/routers/chat.py`
- `backend/modules/observability.py`
- `backend/modules/schemas.py`
- `backend/main.py`
- `frontend/components/Chat/ChatInterface.tsx`
- `frontend/components/console/tabs/TrainingTab.tsx`
- `frontend/components/training/SimulatorView.tsx`
- `backend/database/migrations/migration_interaction_context_training_sessions.sql`
- `backend/tests/test_interaction_context.py`
- `backend/tests/test_training_sessions_router.py`
- `docs/architecture/PERSONA_PIPELINE_V1.md`
- `docs/ops/PERSONA_QUALITY_GATE.md`
- `docs/architecture/INTERACTION_CONTEXT_V1.md`
- `backend/tests/test_chat_interaction_context.py`

## Behavior Proof
### 1) Client mode spoofing is ignored
- Test: `test_owner_chat_ignores_client_mode_spoof`
- File: `backend/tests/test_chat_interaction_context.py`
- Assertion highlights:
  - response metadata `interaction_context == owner_chat`
  - identity gate mode forced to `owner`

### 2) Owner training context is enforced by active training session
- Test: `test_owner_training_context_with_active_session`
- File: `backend/tests/test_chat_interaction_context.py`
- Assertion highlights:
  - response metadata `interaction_context == owner_training`
  - `training_session_id` propagated

### 3) Visitor cannot spoof owner training
- Test: `test_visitor_cannot_spoof_owner_training`
- File: `backend/tests/test_chat_interaction_context.py`
- Assertion highlights:
  - response metadata `interaction_context == public_widget`
  - identity gate mode forced to `public`

### 4) Strict context transition reset (new step)
- Test: `test_context_mismatch_forces_new_conversation`
- File: `backend/tests/test_chat_interaction_context.py`
- Assertion highlights:
  - metadata includes `forced_new_conversation == true`
  - metadata includes `previous_conversation_id`
  - metadata `conversation_id` changed to server-created conversation
  - metadata contains context reset reason (`context_mismatch:*`)

### 5) Public share context trace is preserved
- Test: `test_public_share_clarify_uses_public_context_and_mode`
- File: `backend/tests/test_chat_interaction_context.py`
- Assertion highlights:
  - response `interaction_context == public_share`
  - `share_link_id` trace present

## Migration + DB Proof
### Migration file
- `backend/database/migrations/migration_interaction_context_training_sessions.sql`
- Includes:
  - `training_sessions` table
  - `conversations` context columns
  - `messages.interaction_context`
  - RLS enabled on `training_sessions`
  - tenant isolation policies for `training_sessions`

### Applied in Supabase project
- Project: `verified-digital-twin-brain` (`jvtffdbuwyhmcynauety`)
- Applied migrations:
  - `interaction_context_training_sessions`
  - `interaction_context_training_sessions_rls`

## Command Evidence
### Backend tests
Command:
```bash
pytest -q backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py
```
Result:
- `11 passed`

### Frontend type safety
Command:
```bash
npm --prefix frontend run typecheck
```
Result:
- `tsc --noEmit` passed

### Frontend lint (touched files)
Command:
```bash
npm --prefix frontend run lint -- components/training/SimulatorView.tsx components/console/tabs/TrainingTab.tsx components/Chat/ChatInterface.tsx
```
Result:
- no errors
- warnings remain (pre-existing typing/hook warnings, non-blocking)

### Phase 0 baseline eval harness capture
Command:
```bash
python backend/eval/runner.py 5dd06bcb-9afa-4174-a9bf-308dcf4108c3
```
Result artifact:
- `docs/ai/improvements/proof_outputs/phase0_eval_baseline_20260208_195550.json`
Observed summary:
- `total_questions=35`
- `answered=29`
- `refused=6`
- `errors=0`
- `avg_context_precision=0.0` (baseline indicates retrieval quality gaps to fix in later phases)

## Runtime Contract Added
- Server resolves context from trusted signals only.
- If provided `conversation_id` context does not match resolved context:
  - request is automatically moved to a new server-created conversation
  - trace emits:
    - `forced_new_conversation`
    - `previous_conversation_id`
    - `context_reset_reason`
    - `effective_conversation_id`
- Frontend now updates local conversation state when server returns a different `conversation_id`.

## Phase 0 Contract Docs Proof
- Added:
  - `docs/architecture/PERSONA_PIPELINE_V1.md`
  - `docs/ops/PERSONA_QUALITY_GATE.md`
  - `docs/architecture/INTERACTION_CONTEXT_V1.md`
- These documents lock:
  - runtime pipeline order
  - quality gate metrics/thresholds
  - immutable context derivation and reset semantics
