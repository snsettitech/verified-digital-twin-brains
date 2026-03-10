# Phase 6 Persona Regression + CI Gate Proof (2026-02-09)

## Scope
This proof covers Phase 6 foundation delivery:
- 100+ golden regression cases across the intent taxonomy
- adversarial drift-resistance cases
- channel-isolation/tamper checks
- blocking CI workflow for persona regression

## Files Delivered
- `backend/eval/persona_regression_runner.py`
- `backend/eval/persona_regression_dataset.json`
- `backend/tests/test_persona_regression_runner.py`
- `.github/workflows/persona-regression.yml`
- `docs/ops/QUALITY_GATE.md`
- `docs/ops/PERSONA_QUALITY_GATE.md`

## Dataset Coverage
- Dataset file: `backend/eval/persona_regression_dataset.json`
- Version: `phase6_v1`
- Total prompt cases: `104`
  - Standard: `64` (8 intents x 8 each)
  - Adversarial: `40` (8 intents x 5 each)
- Channel isolation checks: `6`
  - owner mode spoof ignored
  - owner active training session
  - inactive training fallback
  - visitor training spoof blocked
  - public share context resolution
  - training-write blocked in public context

## Blocking Gate Contract
- Runner:
```bash
python backend/eval/persona_regression_runner.py \
  --dataset backend/eval/persona_regression_dataset.json \
  --min-pass-rate 0.95 \
  --min-adversarial-pass-rate 0.95 \
  --min-channel-isolation-pass-rate 1.0
```
- Gate thresholds:
  - `pass_rate >= 0.95`
  - `adversarial_pass_rate >= 0.95`
  - `channel_isolation_pass_rate == 1.0`
- CI workflow:
  - `.github/workflows/persona-regression.yml`
  - Runs targeted persona/context tests + blocking runner (no `continue-on-error`)

## Validation Evidence
- Regression runner command:
```bash
python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --output docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209.json --min-pass-rate 0.95 --min-adversarial-pass-rate 0.95 --min-channel-isolation-pass-rate 1.0
```
- Result summary:
  - `total_cases=104`
  - `passed_cases=104`
  - `pass_rate=1.0`
  - `adversarial_pass_rate=1.0`
  - `channel_isolation_pass_rate=1.0`
  - `gate.passed=true`

- Test command:
```bash
pytest -q backend/tests/test_persona_regression_runner.py backend/tests/test_persona_compiler.py backend/tests/test_persona_fingerprint_gate.py backend/tests/test_persona_auditor.py backend/tests/test_chat_interaction_context.py backend/tests/test_interaction_context.py backend/tests/test_training_sessions_router.py backend/tests/test_decision_capture_router.py backend/tests/test_persona_specs_router.py backend/tests/test_persona_prompt_optimizer.py backend/tests/test_persona_prompt_variant_store.py backend/tests/test_persona_module_store.py backend/tests/test_persona_intents.py
```
- Result: `40 passed`

- Frontend typecheck:
```bash
cmd /c npm --prefix frontend run typecheck
```
- Result: pass

## Output Artifact
- `docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209.json`
