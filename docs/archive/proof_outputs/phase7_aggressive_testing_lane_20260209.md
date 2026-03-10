# Phase 7 Aggressive Testing Lane Proof (2026-02-09)

## Scope delivered
- Aggressive role-play + retraining convergence runner.
- Blind persona recognizability scorer.
- Reusable channel-isolation check module.
- Convergence gate utility.
- Nightly CI workflow for aggressive lane.
- Regression runner refactor to shared channel-isolation module.

## Changed files
- `.github/workflows/persona-aggressive-nightly.yml`
- `backend/eval/persona_aggressive_runner.py`
- `backend/eval/persona_blind_recognition.py`
- `backend/eval/persona_channel_isolation.py`
- `backend/eval/persona_convergence_gate.py`
- `backend/eval/persona_regression_runner.py`
- `backend/eval/persona_roleplay_scenarios.json`
- `backend/tests/test_persona_aggressive_runner.py`
- `backend/tests/test_persona_blind_recognition.py`
- `backend/tests/test_persona_channel_isolation.py`
- `backend/tests/test_persona_convergence_gate.py`

## Validation commands and results
1. Test lane
   - Command:
     - `pytest -q backend/tests/test_persona_channel_isolation.py backend/tests/test_persona_blind_recognition.py backend/tests/test_persona_convergence_gate.py backend/tests/test_persona_aggressive_runner.py backend/tests/test_persona_regression_runner.py`
   - Result:
     - `5 passed`

2. Aggressive role-play convergence run
   - Command:
     - `python backend/eval/persona_aggressive_runner.py --dataset backend/eval/persona_roleplay_scenarios.json --output docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209.json --max-cycles 6 --required-consecutive 3 --scenario-multiplier 8 --persona-recognizability-min 0.80 --post-rewrite-compliance-min 0.88 --citation-validity-min 0.95 --clarification-correctness-min 0.85 --invalid-policy-transitions-max 0 --rewrite-rate-max 0.30 --latency-delta-max 0.25 --public-context-training-writes-max 0 --unpublished-leakage-max 0`
   - Result summary:
     - `converged=true`
     - `total_cycles_executed=5`
     - `final persona_recognizability=1.0`
     - `final post_rewrite_compliance=1.0`
     - `final citation_validity=1.0`
     - `final clarification_correctness=1.0`
     - `final rewrite_rate=0.0938`
     - `final latency_delta=0.0885`
     - `final total_cases=192` (scenario multiplier 8)

3. Phase 6 regression recheck (post-refactor)
   - Command:
     - `python backend/eval/persona_regression_runner.py --dataset backend/eval/persona_regression_dataset.json --output docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209_recheck.json --min-pass-rate 0.95 --min-adversarial-pass-rate 0.95 --min-channel-isolation-pass-rate 1.0`
   - Result summary:
     - `total_cases=104`
     - `pass_rate=1.0`
     - `adversarial_pass_rate=1.0`
     - `channel_isolation_pass_rate=1.0`
     - `gate.passed=true`

## Artifacts
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209.json`
- `docs/ai/improvements/proof_outputs/phase7_aggressive_roleplay_result_20260209_transcripts.json`
- `docs/ai/improvements/proof_outputs/phase6_persona_regression_result_20260209_recheck.json`
