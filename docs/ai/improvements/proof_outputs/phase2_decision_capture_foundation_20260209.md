# Phase 2 Decision Capture Foundation Proof (2026-02-09)

## Scope
This proof covers Phase 2 backend foundations:
- decision-trace capture APIs (`sjt`, `pairwise`, `introspection`)
- strict `owner_training` write gating
- persistence for traces/preferences/introspection
- derived procedural module candidate creation
- migration + RLS rollout

## Delivered Files
- `backend/modules/interaction_context.py`
  - added `require_owner_training_context(...)`
- `backend/modules/decision_capture_store.py`
- `backend/routers/decision_capture.py`
- `backend/database/migrations/migration_phase2_decision_capture.sql`
- `backend/main.py` (router registration)
- `backend/tests/test_decision_capture_router.py`
- `backend/tests/test_interaction_context.py` (training-write helper coverage)

## API Endpoints Implemented
- `POST /twins/{twin_id}/decision-capture/sjt`
- `POST /twins/{twin_id}/decision-capture/pairwise`
- `POST /twins/{twin_id}/decision-capture/introspection`

## Enforcement Behavior
- All decision-capture writes require:
  - authenticated owner
  - twin access check
  - active twin
  - active training session context (`owner_training`)
- If request is not in owner training context, endpoint returns `403`.

## Data Model Implemented
- `persona_decision_traces`
- `persona_preferences`
- `persona_introspection`
- `persona_modules` (draft module candidates derived from captures)

## Clause + Module Derivation
- Stable clause IDs generated per record type:
  - `POL_DECISION_*` for SJT
  - `POL_STYLE_*` for pairwise
  - `POL_PROCESS_*` for introspection
- Each capture also inserts a draft `persona_modules` candidate row with:
  - `module_id`
  - `intent_label`
  - `module_data`
  - `source_event_type/source_event_id`

## Migration Proof
- Local migration file:
  - `backend/database/migrations/migration_phase2_decision_capture.sql`
- Applied to Supabase project `jvtffdbuwyhmcynauety`:
  - migration name: `phase2_decision_capture`
- Confirmed in migration list:
  - includes `20260209013020 phase2_decision_capture`

## Test Evidence
### Backend
Command:
```bash
pytest -q backend/tests/test_decision_capture_router.py backend/tests/test_interaction_context.py backend/tests/test_persona_specs_router.py backend/tests/test_persona_compiler.py backend/tests/test_chat_interaction_context.py backend/tests/test_training_sessions_router.py
```
Result:
- `21 passed`

### Frontend safety check
Command:
```bash
npm --prefix frontend run typecheck
```
Result:
- `tsc --noEmit` passed

## Security Advisor Note
- Post-migration security advisors were re-checked.
- Existing historical project lints remain (for unrelated legacy tables/functions), but no new phase2 table-specific RLS-disable lint was introduced.
