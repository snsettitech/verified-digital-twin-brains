# Langfuse P1 Implementation Summary

## Overview
This document summarizes the P1 (Priority 1) Langfuse observability enhancements implemented in the codebase.

---

## Phase 1: Frontend Trace ID Propagation ✅

### Goal
Link UI actions to backend traces for end-to-end visibility

### Implementation

#### Frontend Changes
**File:** `frontend/components/Chat/ChatInterface.tsx`

- Generate `trace_id` using `crypto.randomUUID()` before each chat request
- Pass `trace_id` in custom header `X-Langfuse-Trace-Id`
- Also include in request body as `trace_id` field

```typescript
const traceId = crypto.randomUUID();
const response = await fetch(`${apiBaseUrl}/chat/${twinId}`, {
  headers: {
    'Content-Type': 'application/json',
    'X-Langfuse-Trace-Id': traceId,
  },
  body: JSON.stringify({
    query: text,
    trace_id: traceId,
  }),
});
```

#### Backend Changes
**Files:** 
- `backend/modules/schemas.py` - Added `trace_id` to ChatRequest and PublicChatRequest
- `backend/routers/chat.py` - Extract trace_id from header and use it

```python
@router.post("/chat/{twin_id}")
async def chat(
    twin_id: str, 
    request: ChatRequest, 
    user=Depends(get_current_user),
    x_langfuse_trace_id: Optional[str] = Header(None, alias="X-Langfuse-Trace-Id")
):
    trace_id = x_langfuse_trace_id or request.trace_id
    if trace_id:
        langfuse_context.update_current_trace(id=trace_id)
```

### What You Get
- Click a trace in Langfuse dashboard → see the exact UI interaction that caused it
- Frontend and backend logs linked by the same trace_id
- Debug user issues by searching for their specific trace_id

---

## Phase 2: Langfuse Prompt Management ✅

### Goal
Store prompts in Langfuse for version control and A/B testing

### Implementation

**New File:** `backend/modules/langfuse_prompt_manager.py`

#### Key Features
1. **Fetch from Langfuse cloud** with automatic fallback to local files
2. **Compile prompts** with variable substitution
3. **Track prompt usage** in traces automatically
4. **Cache prompts** locally for performance

```python
from modules.langfuse_prompt_manager import compile_prompt

# This will fetch from Langfuse or fallback to local
router_prompt = compile_prompt(
    "router",
    variables={
        "user_query": last_human_msg,
        "interaction_context": interaction_context,
    }
)
```

#### Prompt Tracking
Every prompt usage is automatically tracked:
```python
langfuse_context.update_current_observation(
    metadata={
        "prompt_name": "router",
        "prompt_version": "v1.0",
        "prompt_source": "langfuse",  # or "local_file", "local_default"
    }
)
```

### Prompts Available
- `chat_system` - Main system prompt
- `scribe_extraction` - Knowledge graph extraction
- `hyde_generator` - Hypothetical document generation
- `query_expansion` - Query variation generation
- `style_analyzer` - Writing style analysis
- `router` - Intent classification
- `planner` - Response planning
- `realizer` - Response generation

### What You Get
- Change prompts in Langfuse UI without redeploying
- A/B test different prompt versions
- See which prompt version produced each response
- Rollback bad prompt changes instantly

---

## Phase 3: Automatic LLM Judge Scoring ✅

### Goal
Evaluate every response for quality and flag issues automatically

### Implementation

**New Files:**
- `backend/modules/evaluation_pipeline.py` - Main evaluation orchestrator
- Updated `backend/eval/judges.py` - Added `judge_response_completeness`

#### Judges Implemented

1. **Faithfulness Judge**
   - Checks if answer matches retrieved context
   - Score: 0.0-1.0
   - Flags: `low_faithfulness`

2. **Citation Alignment Judge**
   - Verifies citations support the claims
   - Score: 0.0-1.0
   - Flags: `low_citation_alignment`

3. **Completeness Judge**
   - Evaluates if answer fully addresses the query
   - Score: 0.0-1.0
   - Flags: `low_completeness`

#### Integration

Evaluation runs automatically after each chat response:

```python
# In backend/routers/chat.py
from modules.evaluation_pipeline import evaluate_response_async

evaluate_response_async(
    trace_id=current_trace_id,
    query=query,
    response=full_response,
    context=context_text,
    citations=citations
)
```

This is **fire-and-forget** (non-blocking) - it doesn't slow down the response.

#### Scores Logged to Langfuse

```python
# Individual scores
client.score(trace_id=trace_id, name="faithfulness", value=0.85)
client.score(trace_id=trace_id, name="citation_alignment", value=0.92)
client.score(trace_id=trace_id, name="completeness", value=0.78)

# Overall score
client.score(trace_id=trace_id, name="overall_quality", value=0.85)

# Flag for review if needed
client.score(trace_id=trace_id, name="needs_review", value=1)
```

### What You Get
- Dashboard charts showing quality trends over time
- Filter traces by "needs_review = true" to find problematic responses
- Compare scores across different prompt versions
- Get alerted when quality drops

---

## Phase 4: Dataset Collection ✅

### Goal
Build datasets for regression testing and few-shot examples

### Implementation

**New File:** `backend/modules/dataset_builder.py`

#### Auto-Collection Logic

```python
if overall_score >= 0.8:
    # Add to high_quality_responses dataset
    add_to_high_quality_dataset(...)
elif overall_score <= 0.5:
    # Add to needs_improvement dataset
    add_to_improvement_dataset(...)
```

#### Datasets Created

1. **high_quality_responses**
   - Responses scoring >= 0.8
   - Used for: Few-shot examples, regression testing
   - Metadata: scores, trace_id, collection timestamp

2. **needs_improvement**
   - Responses scoring <= 0.5
   - Used for: Identifying issues, training data
   - Metadata: failure reasons, scores, trace_id

#### Integration

Automatically triggered after evaluation:

```python
from modules.dataset_builder import collect_response

collect_response(
    trace_id=trace_id,
    query=query,
    response=response,
    context=context,
    citations=citations,
    scores=scores,
    overall_score=overall_score
)
```

#### Few-Shot Example Fetching

```python
from modules.dataset_builder import get_few_shot_examples

examples = get_few_shot_examples(query_type="stance", n=3)
# Returns top 3 high-quality examples for stance questions
```

### What You Get
- Automatic dataset building without manual work
- Regression testing: "Did my prompt change break these 50 known-good queries?"
- Dynamic few-shot prompting with best examples
- Training data export for fine-tuning

---

## Phase 5: Persona Audit Scoring ✅

### Goal
Track persona compliance metrics in Langfuse

### Implementation

**File:** `backend/routers/chat.py` - Updated `_apply_persona_audit` function

#### Scores Logged

After each persona audit, these scores are logged to Langfuse:

```python
# Structure/Policy compliance score (0.0-1.0)
client.score(name="persona_structure_policy", value=audit.structure_policy_score)

# Voice fidelity score (0.0-1.0)
client.score(name="persona_voice_fidelity", value=audit.voice_score)

# Overall persona score (0.0-1.0)
client.score(name="persona_overall", value=audit.final_persona_score)

# Rewrite flag (boolean)
if audit.rewrite_applied:
    client.score(name="persona_rewrite_applied", value=1)
```

#### Context Tracked

```python
context_trace.update({
    "deterministic_gate_passed": audit.deterministic_gate_passed,
    "structure_policy_score": audit.structure_policy_score,
    "voice_score": audit.voice_score,
    "draft_persona_score": audit.draft_persona_score,
    "final_persona_score": audit.final_persona_score,
    "rewrite_applied": audit.rewrite_applied,
    "rewrite_reason_categories": audit.rewrite_reason_categories,
    "violated_clause_ids": audit.violated_clause_ids,
})
```

### What You Get
- Track persona compliance over time
- See how often rewrites are applied
- Identify which persona rules are violated most
- Compare persona scores across different spec versions

---

## Files Created/Modified

### New Files
1. `backend/modules/langfuse_prompt_manager.py` - Prompt management
2. `backend/modules/evaluation_pipeline.py` - LLM judge orchestration
3. `backend/modules/dataset_builder.py` - Dataset collection

### Modified Files
1. `frontend/components/Chat/ChatInterface.tsx` - Trace ID propagation
2. `backend/modules/schemas.py` - Added trace_id fields
3. `backend/routers/chat.py` - Trace extraction, persona scoring, evaluation
4. `backend/modules/agent.py` - Prompt manager integration
5. `backend/eval/judges.py` - Added completeness judge

---

## Environment Variables

Ensure these are set:
```bash
# Required for all features
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Optional
LANGFUSE_RELEASE=prod-v1.2.3  # Track deployments
```

---

## Usage Examples

### Viewing All Scores in Langfuse

1. Go to Langfuse Dashboard → Traces
2. Click on any trace
3. See nested spans for each phase
4. Click "Scores" tab to view:
   - faithfulness: 0.85
   - citation_alignment: 0.92
   - completeness: 0.78
   - overall_quality: 0.85
   - persona_structure_policy: 0.88
   - persona_voice_fidelity: 0.91
   - persona_overall: 0.90

### Filtering for Review

Filter traces by:
```
scores.needs_review = true
```
Or:
```
scores.overall_quality < 0.7
```

### Comparing Prompt Versions

1. Create two prompt versions in Langfuse
2. Test with same queries
3. Compare scores between versions
4. Choose the better performing one

---

## Next Steps (P2)

1. **Set up Langfuse Alerts** - Get notified when error rate spikes
2. **Implement Regression Testing** - Run dataset against new deployments
3. **Add Few-Shot Prompting** - Use high-quality dataset dynamically
4. **Create Custom Dashboards** - Track key metrics over time
5. **Export for Fine-Tuning** - Use datasets to train custom models
