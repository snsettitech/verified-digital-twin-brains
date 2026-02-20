# Grounded ChatGPT-Like Plan

## Scope
Build generalized document-grounded chat behavior for `/chat/{twin_id}` with deterministic gating, synthesis-first answers, targeted clarifications, and truthful confidence.

## Invariants
- Clarifications are generated only in `backend/modules/agent.py` inside `planner_node`.
- Smalltalk bypass runs before identity gate.
- Pre-agent identity gate does not decide answerability and does not emit clarify/answer content.
- Non-quote turns are synthesized.
- Verbatim extraction is quote-only, strong-evidence-only, and `answer_text`-only.
- Cross-twin retrieval scoping remains enforced.

## Phase Order
1. Phase 0: Baseline lock and telemetry.
2. Phase 0.5: Unified grounding policy module.
3. Phase 1: Gate ordering and identity-gate scope reduction.
4. Phase 2.5: Prompt contamination fix (before retrieval upgrades).
5. Phase 2: Retrieval robustness (hybrid, retry, diversity).
6. Phase 3: Online-eval fallback restrictions.
7. Phase 4: Output discipline and response composer templates.
8. Phase 5: Confidence calibration and UI truthfulness.

## Retrieval Confidence Floor
The floor uses normalized `retrieval_stats`:
- `dense_top1`, `dense_top5_avg`
- `sparse_top1`, `sparse_top5_avg`
- `rerank_top1`, `rerank_top5_avg`
- `evidence_block_counts`

Priority for confidence gate:
1. rerank metrics when present
2. dense metrics
3. sparse metrics

These stats must be emitted in chat debug metadata for every turn.

## Phase Checklists

### Phase 0
- Add per-turn debug snapshot:
  - `query_class`, `requires_evidence`, `quote_intent`
  - `answerability_state`, `planner_action`
  - `retrieval_stats`
  - selected evidence block types
- Add benchmark prompt suites (greeting, identity, procedural, factual, evaluative, insufficient).
- Add baseline report script and artifacts under test fixtures/docs debug.

### Phase 0.5
- Add `backend/modules/grounding_policy.py` with deterministic decision table:
  - `is_smalltalk`, `query_class`, `quote_intent`, `requires_evidence`, `strict_grounding`, `allow_line_extractor`
- Replace duplicated gating logic in `chat.py` and `agent.py`.
- Add parity tests for matrix decisions.

### Phase 1
- Ensure smalltalk bypass runs before identity gate in `chat.py`.
- Disable pre-agent identity-gate clarify/answer branches for `/chat/{twin_id}` runtime flow.
- Ensure non-smalltalk always reaches agent planner for answer vs clarify.

### Phase 2.5
- Stop embedding prompt-style question content as answer-bearing embeddings.
- Persist `block_type` (`prompt_question`, `answer_text`, etc.).
- Penalize/exclude `prompt_question` blocks for identity/basic summary queries unless `answer_text` is unavailable.
- Add regression tests blocking questionnaire dumps.

### Phase 2
- Add sparse lexical retrieval and fuse with dense via weighted RRF.
- Add MMR and per-doc/per-section caps before rerank.
- Add staged retry controlled by grounding policy + retrieval confidence floor.
- Keep twin-scoped retrieval guardrails unchanged.

### Phase 3
- Enforce no-override rule:
  - if planner answerability in `{direct, derivable}` and `quote_intent=false`, online-eval can annotate only.
- Restrict line extractor to quote-only + answer_text-only + strong evidence.

### Phase 4
- Add query-class response composer templates:
  - identity, procedural, factual, evaluative
- Remove non-quote raw snippet fallback.
- Ensure citations map to selected evidence.

### Phase 5
- Calibrate confidence from retrieval stats + answerability + grounding coverage.
- Ensure stream payload always has calibrated confidence.
- Update UI badge behavior to avoid default 100% drift.

## Regression Matrix
- `hi` -> greeting, no retrieval/evaluator/clarifier.
- `who are you` / `tell me about yourself` -> synthesized identity, no questionnaire dump.
- `how to use this twin?` -> derivable synthesis if evidence exists, no clarifications.
- weak evidence -> retrieval retries before clarification; max 3 targeted questions.
- verbatim only for explicit quote intent.
- online-eval never overrides synthesized non-quote answers.
- confidence reflects grounding strength and answerability.
