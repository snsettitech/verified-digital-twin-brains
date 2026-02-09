# Persona Quality Gate

## Purpose
Define measurable release gates for persona consistency and policy compliance.

## KPIs
- `persona_compliance_score`
- `rewrite_rate`
- `clarification_correctness_rate`
- `style_drift_rate`
- `citation_validity_rate` (citation-required intents)
- `invalid_gate_transition_count`
- `p95_latency_delta`

## Default Thresholds
- Post-rewrite persona compliance: `>= 0.88`
- Citation validity on citation-required intents: `>= 0.95`
- Clarification correctness: `>= 0.85`
- Regression suite pass rate: `>= 0.95`
- Invalid gate transitions: `0`
- P95 latency delta vs baseline: `<= 25%`
- Rewrite rate target after stabilization window: `< 30%`

## Gate Levels
1. Local gate:
   - target backend tests pass
   - target frontend typecheck pass
2. CI gate:
   - persona regression suite pass threshold met
   - policy traversal validity checks pass
3. Release gate:
   - KPI thresholds met on latest staging run
   - trace/audit UX confirms deterministic path and evidence signals

## Required Evidence Per Deliverable
- Changed file list
- Test commands and pass/fail counts
- Runtime verification notes (API/UI behavior)
- Migration application evidence (if schema changed)
- Linked proof artifact in `docs/ai/improvements/proof_outputs/`

## Current Baseline Snapshot
- Context and training-session enforcement tests: passing.
- Conversation context reset under mismatch: passing.
- Proof artifact: `docs/ai/improvements/proof_outputs/interaction_context_guard_20260209.md`

## Pending for Full Phase 0 Exit
- Baseline eval-harness run captured against target twin dataset.
- KPI dashboards wired into release checks.

## Phase 6 Regression Gate (Blocking)
- Runner: `backend/eval/persona_regression_runner.py`
- Dataset: `backend/eval/persona_regression_dataset.json` (104 cases; intent-balanced + adversarial + channel isolation checks)
- CI Workflow: `.github/workflows/persona-regression.yml`
- Hard fail thresholds:
  - `pass_rate >= 0.95`
  - `adversarial_pass_rate >= 0.95`
  - `channel_isolation_pass_rate == 1.0`
