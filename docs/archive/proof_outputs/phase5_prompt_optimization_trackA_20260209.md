# Phase 5 Prompt Optimization Track A Proof (2026-02-09)

## Scope
This proof covers Phase 5 Track A delivery:
- typed prompt render variants for persona compiler
- offline regression-driven variant optimization runner
- evolve-prompts integration for persona mode
- runtime activation and use of best prompt variant
- persistence for optimization runs and prompt variants

## Files Delivered
- `backend/eval/persona_prompt_optimizer.py`
- `backend/eval/persona_prompt_optimization_dataset.json`
- `.agent/tools/evolve_prompts.py`
- `backend/modules/persona_prompt_variant_store.py`
- `backend/modules/persona_compiler.py`
- `backend/modules/agent.py`
- `backend/routers/chat.py`
- `backend/routers/persona_specs.py`
- `backend/database/migrations/migration_phase5_persona_prompt_optimization.sql`
- `backend/tests/test_persona_prompt_optimizer.py`
- `backend/tests/test_persona_prompt_variant_store.py`
- `backend/tests/test_persona_specs_router.py`
- `backend/tests/test_persona_compiler.py`

## Runtime/Behavior Contract Delivered
1. Prompt rendering is variant-aware via typed options:
   - `baseline_v1`
   - `compact_v1`
   - `compact_no_examples_v1`
   - `voice_focus_v1`
2. Optimizer mutates candidate variants and evaluates against a persona dataset.
3. Optimizer ranks variants by objective score and can activate best variant.
4. Runtime prompt assembly reads active variant and compiles/render accordingly.
5. Chat trace metadata now includes `persona_prompt_variant`.
6. Owner endpoints added for optimization operations:
   - `GET /twins/{twin_id}/persona-prompt-variants`
   - `POST /twins/{twin_id}/persona-prompt-variants/{variant_id}/activate`
   - `POST /twins/{twin_id}/persona-prompt-optimization/runs`

## Migration Evidence
- Migration file:
  - `backend/database/migrations/migration_phase5_persona_prompt_optimization.sql`
- Applied to Supabase project `jvtffdbuwyhmcynauety`:
  - migration name: `phase5_persona_prompt_optimization`
  - listed version: `20260209024144`
- SQL verification snapshots:
  - `select count(*) from persona_prompt_optimization_runs;` -> `>=1`
  - active variant row exists for twin `5dd06bcb-9afa-4174-a9bf-308dcf4108c3` with `variant_id=compact_v1`, `status=active`

## Optimization Run Evidence
- CLI run (no DB writes):
```bash
python backend/eval/persona_prompt_optimizer.py --mode heuristic --dataset backend/eval/persona_prompt_optimization_dataset.json --output docs/ai/improvements/proof_outputs/phase5_prompt_optimizer_summary_20260209.json
```
- CLI run (persist + activate best):
```bash
python .agent/tools/evolve_prompts.py --mode persona --generator-mode heuristic --twin-id 5dd06bcb-9afa-4174-a9bf-308dcf4108c3 --persist --apply-best --dataset backend/eval/persona_prompt_optimization_dataset.json --output docs/ai/improvements/proof_outputs/phase5_evolve_prompts_persist_20260209.json
```
- Result snapshot:
  - `candidate_count=7`
  - `best_variant=compact_v1`
  - `best_objective_score=0.518901`

## Test Evidence
- Command:
```bash
pytest -q backend/tests/test_persona_compiler.py backend/tests/test_persona_specs_router.py backend/tests/test_persona_prompt_optimizer.py backend/tests/test_persona_prompt_variant_store.py backend/tests/test_persona_auditor.py backend/tests/test_persona_fingerprint_gate.py backend/tests/test_persona_module_store.py backend/tests/test_persona_intents.py
```
- Result: `20 passed`

- Command:
```bash
pytest -q backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py backend/tests/test_decision_capture_router.py
```
- Result: `18 passed`

- Frontend typecheck:
```bash
cmd /c npm --prefix frontend run typecheck
```
- Result: pass

## Output Artifacts
- `docs/ai/improvements/proof_outputs/phase5_prompt_optimizer_summary_20260209.json`
- `docs/ai/improvements/proof_outputs/phase5_evolve_prompts_persona_20260209.json`
- `docs/ai/improvements/proof_outputs/phase5_evolve_prompts_persist_20260209.json`

## Security Advisor Snapshot
- Ran Supabase security advisors after migration.
- Result: existing project-level lints remain (not introduced by Phase 5 tables), including:
  - `policy_exists_rls_disabled` on legacy `public.users`
  - `rls_disabled_in_public` on legacy public tables
  - `function_search_path_mutable` on legacy functions
- Remediation references:
  - https://supabase.com/docs/guides/database/database-linter?lint=0007_policy_exists_rls_disabled
  - https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public
  - https://supabase.com/docs/guides/database/database-linter?lint=0011_function_search_path_mutable
