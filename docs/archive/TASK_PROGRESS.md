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

## Persona Consistency Execution Update (2026-02-09)
### Completed in this batch
1. Added strict interaction-context guard in chat runtime:
   - If context changes (example: `owner_chat` -> `owner_training`) for an existing conversation, server forces a new conversation.
   - Trace fields now include forced reset indicators.
2. Added owner training session lifecycle and immutable context propagation:
   - Start/stop/active endpoints.
   - `training_session_id` accepted by chat request schema and resolved server-side.
3. Applied and hardened migration:
   - `migration_interaction_context_training_sessions.sql`
   - `training_sessions` RLS + tenant isolation policies.
4. Updated frontend to follow server-issued conversation IDs after context resets.
5. Delivered Phase 1 persona foundation:
   - versioned persona spec schema + validator
   - typed `PromptPlan` compiler with deterministic ordering
   - persona spec CRUD/generate/publish APIs
   - runtime hook in agent prompt builder for active persona specs
   - applied `persona_specs_v1` migration with tenant-scoped RLS
6. Delivered Phase 2 decision-capture foundation:
  - added SJT/pairwise/introspection capture APIs
  - enforced active `owner_training` context for training writes
  - persisted traces in dedicated tables
  - generated draft procedural module candidates with stable clause IDs
  - applied `phase2_decision_capture` migration with tenant-scoped RLS
7. Delivered Phase 3 intent-aware procedural retrieval foundation:
  - added stable runtime intent taxonomy + classifier (`backend/modules/persona_intents.py`)
  - added intent-scoped procedural module retrieval from `persona_modules` (`backend/modules/persona_module_store.py`)
  - merged runtime modules into typed `PromptPlan` compiler path (`backend/modules/persona_compiler.py`)
  - wired runtime trace fields (`intent_label`, `module_ids`) through agent and chat/public/widget responses
  - applied `phase3_persona_module_retrieval` migration for runtime lookup indexes
8. Delivered Phase 4 persona enforcement loop foundation:
  - added deterministic fingerprint gate (`backend/modules/persona_fingerprint_gate.py`)
  - added orchestration for structure/voice judges + clause-targeted rewrite (`backend/modules/persona_auditor.py`)
  - extended judge library with Judge A / Judge B / rewrite helper (`backend/eval/judges.py`)
  - enforced audit/rewrite before final response in owner, widget, and public chat paths (`backend/routers/chat.py`)
  - persisted audit traces via `persona_judge_results` table and applied `phase4_persona_audit` migration

### Validation proof
- Backend tests:
  - `pytest -q backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py`
  - Result: `11 passed`
- Frontend typecheck:
  - `npm --prefix frontend run typecheck`
  - Result: pass
- Phase 0 baseline eval:
  - `python backend/eval/runner.py 5dd06bcb-9afa-4174-a9bf-308dcf4108c3`
  - Artifact: `docs/ai/improvements/proof_outputs/phase0_eval_baseline_20260208_195550.json`
  - Baseline summary: `answered=29/35`, `refused=6`, `avg_context_precision=0.0`
- Full proof artifact:
  - `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`
  - `docs/ai/improvements/proof_outputs/persona_specs_phase1_foundation_20260209.md`
  - `docs/ai/improvements/proof_outputs/phase2_decision_capture_foundation_20260209.md`
  - `docs/ai/improvements/proof_outputs/phase3_intent_aware_procedural_retrieval_20260209.md`
  - `docs/ai/improvements/proof_outputs/phase4_persona_enforcement_loop_20260209.md`
- Phase 4 validation run:
  - `pytest -q backend/tests/test_persona_fingerprint_gate.py backend/tests/test_persona_auditor.py backend/tests/test_chat_interaction_context.py backend/tests/test_persona_compiler.py backend/tests/test_persona_intents.py backend/tests/test_persona_module_store.py backend/tests/test_decision_capture_router.py backend/tests/test_interaction_context.py backend/tests/test_persona_specs_router.py backend/tests/test_training_sessions_router.py`
  - Result: `31 passed`

## Persona Consistency Execution Update (Phase 5 - 2026-02-09)
### Completed in this batch
1. Delivered Phase 5 Track A optimization foundation:
   - added variant-aware prompt rendering (`baseline_v1`, `compact_v1`, `compact_no_examples_v1`, `voice_focus_v1`)
   - added offline optimizer runner and dataset
   - added persona-mode `.agent/tools/evolve_prompts.py` integration
2. Added optimization persistence and activation path:
   - new tables: `persona_prompt_optimization_runs`, `persona_prompt_variants`
   - new store helpers and activation logic
   - runtime now reads active prompt variant for prompt compilation/rendering
3. Added owner APIs for operations:
   - list variants
   - activate variant
   - run optimization and persist + optionally activate best
4. Extended runtime trace metadata:
   - `persona_prompt_variant` included in chat trace metadata and propagated from agent outputs

### Validation proof
- Backend tests:
  - `pytest -q backend/tests/test_persona_compiler.py backend/tests/test_persona_specs_router.py backend/tests/test_persona_prompt_optimizer.py backend/tests/test_persona_prompt_variant_store.py backend/tests/test_persona_auditor.py backend/tests/test_persona_fingerprint_gate.py backend/tests/test_persona_module_store.py backend/tests/test_persona_intents.py`
  - Result: `20 passed`
- Interaction-context regression set:
  - `pytest -q backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py backend/tests/test_decision_capture_router.py`
  - Result: `18 passed`
- Frontend typecheck:
  - `npm --prefix frontend run typecheck`
  - Result: pass
- Migration applied:
  - `phase5_persona_prompt_optimization`
  - version `20260209024144`
- Optimization run artifacts:
  - `docs/ai/improvements/proof_outputs/phase5_prompt_optimizer_summary_20260209.json`
  - `docs/ai/improvements/proof_outputs/phase5_evolve_prompts_persona_20260209.json`
  - `docs/ai/improvements/proof_outputs/phase5_evolve_prompts_persist_20260209.json`
- Full proof note:
  - `docs/ai/improvements/proof_outputs/phase5_prompt_optimization_trackA_20260209.md`

## Persona Consistency Execution Update (Phase 6 - 2026-02-09)
### Completed in this batch
1. Delivered Phase 6 regression suite foundation:
   - added deterministic regression runner with gating thresholds
   - added 104-case golden dataset (intent-balanced + adversarial)
   - added explicit channel-isolation/tamper checks in runner
2. Added blocking CI gate:
   - workflow `.github/workflows/persona-regression.yml`
   - blocking execution of persona regression runner with thresholds
3. Updated ops quality gate docs:
   - `docs/ops/QUALITY_GATE.md`
   - `docs/ops/PERSONA_QUALITY_GATE.md`

### Validation proof
- Regression run:
  - `python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --output docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209.json --min-pass-rate 0.95 --min-adversarial-pass-rate 0.95 --min-channel-isolation-pass-rate 1.0`
  - Result: `total_cases=104`, `pass_rate=1.0`, `adversarial_pass_rate=1.0`, `channel_isolation_pass_rate=1.0`, `gate.passed=true`
- Backend tests:
  - `pytest -q backend/tests/test_persona_regression_runner.py backend/tests/test_persona_compiler.py backend/tests/test_persona_fingerprint_gate.py backend/tests/test_persona_auditor.py backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py backend/tests/test_decision_capture_router.py backend/tests/test_persona_specs_router.py backend/tests/test_persona_prompt_optimizer.py backend/tests/test_persona_prompt_variant_store.py backend/tests/test_persona_module_store.py backend/tests/test_persona_intents.py`
  - Result: `40 passed`
- Frontend typecheck:
  - `npm --prefix frontend run typecheck`
  - Result: pass

### Artifacts
- `backend/eval/persona_regression_runner.py`
- `backend/eval/persona_regression_dataset.json`
- `backend/tests/test_persona_regression_runner.py`
- `.github/workflows/persona-regression.yml`
- `docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209.json`
- `docs/ai/improvements/proof_outputs/phase6_persona_regression_ci_gate_20260209.md`

## Persona Consistency Execution Update (Phase 7 Aggressive Testing - 2026-02-09)
### Completed in this batch
1. Delivered aggressive role-play twin-factory evaluator:
   - `backend/eval/persona_aggressive_runner.py`
   - iterative retraining loop with convergence gating and transcript artifacts
2. Delivered reusable aggressive test primitives:
   - blind recognizability scorer: `backend/eval/persona_blind_recognition.py`
   - convergence gate: `backend/eval/persona_convergence_gate.py`
   - shared channel-isolation checks: `backend/eval/persona_channel_isolation.py`
   - role-play scenario corpus: `backend/eval/persona_roleplay_scenarios.json`
3. Wired nightly CI gate:
   - `.github/workflows/persona-aggressive-nightly.yml`
   - runs role-play convergence gate and uploads summary + transcript artifacts
4. Refactored Phase 6 runner to reuse shared channel-isolation module:
   - updated `backend/eval/persona_regression_runner.py`

### Validation proof
- Aggressive lane tests:
  - `pytest -q backend/tests/test_persona_channel_isolation.py backend/tests/test_persona_blind_recognition.py backend/tests/test_persona_convergence_gate.py backend/tests/test_persona_aggressive_runner.py backend/tests/test_persona_regression_runner.py`
  - Result: `5 passed`
- Aggressive role-play run:
  - `python backend/eval/persona_aggressive_runner.py --dataset backend/eval/persona_roleplay_scenarios.json --output docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209.json --max-cycles 6 --required-consecutive 3 --scenario-multiplier 8 --persona-recognizability-min 0.80 --post-rewrite-compliance-min 0.88 --citation-validity-min 0.95 --clarification-correctness-min 0.85 --invalid-policy-transitions-max 0 --rewrite-rate-max 0.30 --latency-delta-max 0.25 --public-context-training-writes-max 0 --unpublished-leakage-max 0`
  - Result: `converged=true`, `cycles=5`, `total_cases_per_final_cycle=192`, `rewrite_rate=0.0938`, `recognizability=1.0`
- Regression recheck after refactor:
  - `python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --output docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209_recheck.json --min-pass-rate 0.95 --min-adversarial-pass-rate 0.95 --min-channel-isolation-pass-rate 1.0`
  - Result: `pass_rate=1.0`, `adversarial_pass_rate=1.0`, `channel_isolation_pass_rate=1.0`, `gate.passed=true`

### Artifacts
- `backend/eval/persona_aggressive_runner.py`
- `backend/eval/persona_roleplay_scenarios.json`
- `backend/eval/persona_blind_recognition.py`
- `backend/eval/persona_convergence_gate.py`
- `backend/eval/persona_channel_isolation.py`
- `backend/tests/test_persona_aggressive_runner.py`
- `backend/tests/test_persona_blind_recognition.py`
- `backend/tests/test_persona_convergence_gate.py`
- `backend/tests/test_persona_channel_isolation.py`
- `.github/workflows/persona-aggressive-nightly.yml`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209.json`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209_transcripts.json`
- `docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209_recheck.json`

## Persona Consistency Execution Update (Phase 7 UI E2E - 2026-02-09)
### Completed in this batch
1. Implemented pending UI E2E additions from the aggressive testing plan:
   - `frontend/tests/e2e/persona_training_loop.spec.ts`
   - `frontend/tests/e2e/persona_channel_separation.spec.ts`
   - shared mocks: `frontend/tests/e2e/helpers/personaHarness.ts`
2. Hardened E2E auth bypass behavior for deterministic simulator/public testing:
   - `frontend/components/console/tabs/TrainingTab.tsx`
   - `frontend/components/Chat/ChatInterface.tsx`

### Validation proof
- Playwright run:
  - `cmd /c npx playwright test tests/e2e/persona_training_loop.spec.ts tests/e2e/persona_channel_separation.spec.ts`
  - Result: `2 passed`
- Full frontend E2E regression:
  - `cmd /c npx playwright test`
  - Result: `8 passed, 8 skipped`
- Frontend typecheck:
  - `cmd /c npm run typecheck`
  - Result: pass

### Artifacts
- `docs/ai/improvements/proof_outputs/phase7_ui_e2e_training_channel_20260209.md`

## Persona Consistency Execution Update (Phase 7 Live Model Roleplay - 2026-02-09)
### Completed in this batch
1. Upgraded aggressive runner to support model-in-the-loop generation:
   - added generator modes: `auto | heuristic | openai`
   - added OpenAI-backed draft generation path with resilient fallback
   - added cycle-to-cycle coaching focus carryover from top violated clauses
2. Added regression coverage for the new runner mode:
   - updated `backend/tests/test_persona_aggressive_runner.py` with explicit heuristic-mode assertion
3. Executed live OpenAI roleplay proof runs and stored artifacts.

### Validation proof
- Backend tests:
  - `python -m pytest backend/tests/test_persona_aggressive_runner.py -q`
  - Result: `2 passed`
- Live model roleplay run (baseline):
  - `python backend/eval/persona_aggressive_runner.py --dataset backend/eval/persona_roleplay_scenarios.json --output docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_20260209T042357Z.json --generator-mode openai --model gpt-4o-mini --max-cycles 6 --required-consecutive 3 --scenario-multiplier 1`
  - Result: `converged=true`, `cycles=5`, `final_rewrite_rate=0.2917`
- Live model roleplay run (aggressive):
  - `python backend/eval/persona_aggressive_runner.py --dataset backend/eval/persona_roleplay_scenarios.json --output docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_x2_20260209T042645Z.json --generator-mode openai --model gpt-4o-mini --max-cycles 6 --required-consecutive 3 --scenario-multiplier 2`
  - Result: `converged=true`, `cycles=3`, `final_recognizability=1.0`, `final_post_rewrite_compliance=0.9979`, `final_rewrite_rate=0.2292`

### Artifacts
- `backend/eval/persona_aggressive_runner.py`
- `backend/tests/test_persona_aggressive_runner.py`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_20260209T042357Z.json`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_20260209T042357Z_transcripts.json`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_x2_20260209T042645Z.json`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_live_x2_20260209T042645Z_transcripts.json`
- `docs/ai/improvements/proof_outputs/phase7_live_roleplay_proof_20260209T042645Z.md`

## Persona Consistency Execution Update (Phase 7 Feedback Learning Loop - 2026-02-09)
### Completed in this batch
1. Implemented feedback-learning closed loop:
   - local training-event ingestion for feedback
   - module confidence/status updates from feedback + persona audit outcomes
   - regression gate + optional auto-publish decision
2. Added owner APIs:
   - `GET /twins/{twin_id}/persona-feedback-learning/runs`
   - `POST /twins/{twin_id}/persona-feedback-learning/runs`
3. Added storage schema and RLS:
   - `persona_training_events`
   - `persona_feedback_learning_runs`
4. Applied migration in Supabase project `jvtffdbuwyhmcynauety`:
   - `phase7_feedback_learning_loop` (`success=true`)

### Validation proof
- Compile:
  - `python -m py_compile backend/modules/persona_feedback_learning.py backend/routers/feedback.py backend/routers/persona_specs.py`
- Tests:
  - `python -m pytest backend/tests/test_persona_feedback_learning.py backend/tests/test_feedback_router.py backend/tests/test_persona_specs_router.py -q`
  - Result: `13 passed`
- Runtime loop execution:
  - run id: `2a305de7-dfe6-4160-9a4d-ecb64823ea8f`
  - twin: `5dd06bcb-9afa-4174-a9bf-308dcf4108c3`
  - status: `completed`, gate passed: `true`
  - end-to-end smoke: feedback POST `trace-phase7-learning-smoke-20260209` -> run `3dedc0bb-1521-4639-aec8-ae4da050bf31` with `events_scanned=1`, `events_processed=1`

### Artifacts
- `backend/database/migrations/migration_phase7_feedback_learning_loop.sql`
- `backend/modules/persona_feedback_learning.py`
- `backend/routers/feedback.py`
- `backend/routers/persona_specs.py`
- `backend/tests/test_persona_feedback_learning.py`
- `backend/tests/test_feedback_router.py`
- `docs/ai/improvements/proof_outputs/phase7_feedback_learning_run_20260209T051507Z.json`
- `docs/ai/improvements/proof_outputs/phase7_feedback_learning_smoke_20260209.json`
- `docs/ai/improvements/proof_outputs/phase7_feedback_learning_loop_20260209.md`

## Persona Consistency Execution Update (Phase 7 Feedback Learning Automation - 2026-02-09)
### Completed in this batch
1. Promoted feedback learning to asynchronous background jobs:
   - added `feedback_learning` job type to backend runtime enum
   - added worker dispatch path for `feedback_learning` jobs
2. Enabled automatic enqueue from feedback capture:
   - `POST /feedback/{trace_id}` now attempts non-blocking enqueue per resolved twin
   - enqueue keeps threshold/cooldown/in-flight protections
3. Added scheduler sweep for periodic/nightly operation:
   - `backend/scripts/run_feedback_learning_scheduler.py`
   - supports `--once` and continuous interval mode
4. Applied DB constraint migration for `jobs.job_type`:
   - `migration_add_feedback_learning_job_type.sql`
   - applied in Supabase project `jvtffdbuwyhmcynauety` (`success=true`)
5. Added test coverage for automation path:
   - enqueue decision logic
   - feedback route auto-enqueue integration
   - job processor happy path

### Validation proof
- Focused tests + compile:
  - `python -m pytest backend/tests/test_feedback_router.py backend/tests/test_persona_feedback_learning_jobs.py backend/tests/test_persona_feedback_learning.py backend/tests/test_persona_specs_router.py -q`
  - Result: `17 passed`
  - `python -m py_compile backend/modules/persona_feedback_learning_jobs.py backend/routers/feedback.py backend/worker.py backend/scripts/run_feedback_learning_scheduler.py`
- Runtime smokes:
  - cooldown behavior artifact: `docs/ai/improvements/proof_outputs/phase7_feedback_learning_auto_enqueue_smoke_20260209T054044Z.json`
  - forced queue->process artifact: `docs/ai/improvements/proof_outputs/phase7_feedback_learning_auto_enqueue_force_smoke_20260209T054119Z.json` (`job_status_after=complete`)
- Scheduler proof:
  - `python backend/scripts/run_feedback_learning_scheduler.py --once --min-events 50 --limit-twins 20`
  - artifact: `docs/ai/improvements/proof_outputs/phase7_feedback_learning_scheduler_once_20260209T0541Z.json`

### Artifacts
- `backend/database/migrations/migration_add_feedback_learning_job_type.sql`
- `backend/scripts/run_feedback_learning_scheduler.py`
- `backend/tests/test_persona_feedback_learning_jobs.py`
- `docs/ai/improvements/proof_outputs/phase7_feedback_learning_automation_20260209.md`

## Production Runbook Execution Update (2026-02-09)
### Completed in this batch
1. Fixed production blockers on Render:
   - enforced explicit `ALLOWED_ORIGINS` allowlist for frontend origins
   - set `REDIS_URL` for API + worker
   - set feedback-learning production env controls on both services
2. Triggered and verified live Render deployments:
   - API deploy `dep-d64o5rsr85hc73c0c5dg` -> `live`
   - Worker deploy `dep-d64o5sfgi27c73b622lg` -> `live`
3. Executed runbook smoke validations:
   - API `/health` healthy
   - CORS preflight allow/deny behavior validated
   - worker runtime confirms Redis queue connectivity
   - production frontend domain reachable (`digitalbrains.vercel.app`)

### Validation proof
- Deploy status checks:
  - `mcp__render__get_deploy` for both deploy IDs above
  - Result: both `live`
- Runtime checks:
  - `Invoke-RestMethod https://verified-digital-twin-brains.onrender.com/health`
  - `Invoke-WebRequest` CORS preflight from allowed and blocked origins
  - `mcp__render__list_logs` confirms `[Worker] Connected to Redis queue`
  - `Invoke-WebRequest https://digitalbrains.vercel.app` -> `200`

### Runtime alignment update
- Vercel project `prj_tye8zjjKLvhdjH2pyBXno8JaylYk` reports `nodeVersion=24.x`.
- Updated frontend engine policy in `frontend/package.json` from `20.x` to `>=20 <25`.
- This removes runtime-version mismatch as a production blocker.

### Artifacts
- `docs/ai/improvements/proof_outputs/prod_runbook_execution_20260209T065226Z.json`
- `docs/ai/improvements/proof_outputs/prod_runbook_execution_20260209T065226Z.md`
