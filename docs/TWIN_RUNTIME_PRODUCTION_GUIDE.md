# Twin Runtime Production Guide

## What this adds

This production slice introduces:

1. A strict runtime routing contract per message:
   - `intent`
   - `confidence`
   - `required_inputs_missing`
   - `chosen_workflow`
   - `output_schema`
   - `action` (`answer|clarify|refuse|escalate`)
   - `clarifying_questions`
2. Auditable response lineage:
   - routing decision persistence
   - response audit persistence (sources, confidence, artifacts, refusal/escalation)
3. Owner review queue for uncertain/escalated/refused turns.
4. Typed learning inputs that create new draft persona spec versions.
5. Active Twin Spec endpoint derived from active persona spec.

## Database migration

Apply:

`backend/database/migrations/20260217_twin_runtime_governance.sql`

Creates:

- `conversation_routing_decisions`
- `conversation_response_audits`
- `owner_review_queue`
- `learning_inputs`

All tables include tenant-scoped RLS policies.

## New APIs

### Twin Spec view

- `GET /twins/{twin_id}/twin-spec/active`

Returns normalized Twin Spec generated from active `persona_specs`.

### Owner review queue

- `GET /twins/{twin_id}/owner-review-queue?status=pending`
- `POST /twins/{twin_id}/owner-review-queue/{item_id}/resolve`

### Learning inputs

- `GET /twins/{twin_id}/learning-inputs?status=all`
- `POST /twins/{twin_id}/learning-inputs`
- `POST /twins/{twin_id}/learning-inputs/{learning_input_id}/apply`
- `POST /twins/{twin_id}/learning-inputs/{learning_input_id}/reject`

Supported `input_type` values:

- `add_faq_answer`
- `add_adjust_rubric_rule`
- `add_workflow_step_template`
- `add_guardrail_refusal_rule`
- `add_style_preference`

## Runtime behavior changes

1. `router_node` now emits a strict `routing_decision`.
2. Planner honors `routing_decision.action`:
   - `clarify` -> asks 1-3 clarifying questions
   - `escalate` -> uncertainty + owner-input request
   - `refuse` -> refusal copy
3. Realizer includes `routing_decision` and `workflow_intent` in message metadata.
4. Chat surfaces persist routing + audit records and enqueue owner review when needed.

## Safety and drift controls

1. Learning inputs are typed and auditable.
2. `add_style_preference` cannot modify `identity_voice` unless
   `allow_persona_fundamental_change=true`.
3. Publish/rollback remains through persona spec version endpoints:
   - create/update draft spec
   - publish selected version
   - rollback by publishing a previous version

## Tests and CI

Added tests:

- `backend/tests/test_routing_decision_contract.py`
- `backend/tests/test_agent_planner_routing_decision.py`
- `backend/tests/test_twin_runtime_router.py`
- `backend/tests/test_twin_runtime_eval_dataset.py`

Eval seed dataset:

- `backend/eval/twin_runtime_eval_cases.json`

Suggested CI command:

```bash
python -m pytest \
  backend/tests/test_routing_decision_contract.py \
  backend/tests/test_agent_planner_routing_decision.py \
  backend/tests/test_agent_router_policy.py \
  backend/tests/test_twin_runtime_router.py \
  backend/tests/test_twin_runtime_eval_dataset.py
```

