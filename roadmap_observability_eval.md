# Roadmap: Observability + Evaluation (Epic G)

> Monitor, trace, and measure the quality of the Digital Brain.

## Overview

Implement Langfuse tracing for observability and RAGAS evaluation for RAG quality metrics. Establish baselines and prevent regression.

## Dependencies

- ✅ Epic E (Hybrid Chat) - for tracing chat operations

## Tasks

### G1: Langfuse Integration
**Status**: Not Started
**Estimated**: 3 hours

- [ ] Install langfuse SDK
- [ ] Configure credentials
- [ ] Create trace wrapper utility
- [ ] Add to chat pipeline

**Integration Pattern**:
```python
from langfuse import Langfuse
from langfuse.decorators import observe

langfuse = Langfuse()

@observe()
async def chat(twin_id: UUID, message: str):
    with langfuse.trace(name="chat") as trace:
        # Track retrieval
        with trace.span(name="retrieval"):
            context = await hybrid_retrieve(...)
            trace.span.update(metadata={"docs_found": len(context.documents)})

        # Track generation
        with trace.span(name="generation"):
            response = await generate_response(context)
            trace.span.update(metadata={"tokens_used": response.tokens})

        # Track memory extraction
        with trace.span(name="memory_extraction"):
            await extract_memories(...)

        return response
```

**Acceptance Criteria**:
- All chat interactions traced
- Traces visible in Langfuse dashboard
- Metadata captured for analysis

---

### G2: Trace Retrieval Components
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: G1

- [ ] Trace vector retrieval separately
- [ ] Trace graph retrieval separately
- [ ] Log retrieval scores
- [ ] Log sources used

**Retrieval Spans**:
```python
@observe(name="vector_retrieval")
async def vector_retrieve(...):
    results = await pinecone_query(...)

    # Log to current span
    langfuse.update_current_span(
        metadata={
            "top_score": results[0].score if results else 0,
            "results_count": len(results),
            "namespace": namespace
        }
    )

    return results

@observe(name="graph_retrieval")
async def graph_retrieve(...):
    nodes = await query_graph(...)

    langfuse.update_current_span(
        metadata={
            "nodes_found": len(nodes),
            "entity_types": [n.type for n in nodes]
        }
    )

    return nodes
```

**Acceptance Criteria**:
- Each retrieval type visible in trace
- Scores and counts logged
- Can diagnose retrieval issues

---

### G3: Trace Memory Writes
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: G1

- [ ] Trace memory extraction
- [ ] Log entities extracted
- [ ] Log candidates created
- [ ] Link to source conversation

**Memory Write Spans**:
```python
@observe(name="memory_extraction")
async def extract_and_store_memories(...):
    extraction = await scribe.extract(...)

    langfuse.update_current_span(
        metadata={
            "entities_extracted": len(extraction.entities),
            "facts_extracted": len(extraction.facts),
            "relationships_extracted": len(extraction.relationships)
        }
    )

    candidates = await create_memory_candidates(extraction)

    return candidates
```

**Acceptance Criteria**:
- Memory extraction visible in traces
- Extraction counts logged
- Can analyze extraction quality

---

### G4: RAGAS Evaluation Setup
**Status**: Not Started
**Estimated**: 4 hours

- [ ] Install ragas library
- [ ] Create evaluation dataset
- [ ] Define metrics to track:
  - Faithfulness
  - Answer relevancy
  - Context recall
  - Context precision
- [ ] Create evaluation script

**Evaluation Dataset Format**:
```python
evaluation_dataset = [
    {
        "question": "What's the minimum check size?",
        "answer": "$500K to $2M for Series A",
        "ground_truth": "Minimum check size is $500,000",
        "contexts": ["Investment criteria doc chunk..."]
    },
    ...
]
```

**RAGAS Metrics**:
```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision
)

def run_evaluation(dataset):
    return evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision
        ]
    )
```

**Acceptance Criteria**:
- Evaluation script runs
- Metrics calculated correctly
- Baseline scores recorded

---

### G5: Baseline Recording
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: G4

- [ ] Create initial evaluation dataset (20+ examples)
- [ ] Run baseline evaluation
- [ ] Record scores in docs/eval_baseline.md
- [ ] Set regression thresholds

**Baseline Format**:
```markdown
# Evaluation Baseline - v1.0

Date: 2024-12-24
Dataset: 25 examples

## Scores

| Metric | Score | Threshold |
|--------|-------|-----------|
| Faithfulness | 0.85 | 0.80 |
| Answer Relevancy | 0.82 | 0.75 |
| Context Recall | 0.78 | 0.70 |
| Context Precision | 0.80 | 0.75 |

## Notes
- Initial baseline on VC Brain test data
- Some context precision loss due to graph not fully populated
```

**Acceptance Criteria**:
- Baseline documented
- Thresholds defined
- CI can compare against baseline

---

### G6: CI/CD Evaluation Integration
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: G4, G5

- [ ] Create pytest test for evaluation
- [ ] Run on PR/push to main
- [ ] Fail if below threshold
- [ ] Report scores in PR comment

**CI Test**:
```python
# test_evaluation.py
def test_rag_quality_above_threshold():
    results = run_evaluation(load_eval_dataset())

    assert results["faithfulness"] >= 0.80, f"Faithfulness {results['faithfulness']} below 0.80"
    assert results["answer_relevancy"] >= 0.75, f"Relevancy {results['answer_relevancy']} below 0.75"
    assert results["context_recall"] >= 0.70, f"Recall {results['context_recall']} below 0.70"
    assert results["context_precision"] >= 0.75, f"Precision {results['context_precision']} below 0.75"
```

**GitHub Action**:
```yaml
# .github/workflows/evaluation.yml
name: RAG Evaluation
on: [push, pull_request]
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v4
      - name: Run Evaluation
        run: |
          pip install -r requirements.txt
          pytest tests/test_evaluation.py -v
```

**Acceptance Criteria**:
- Evaluation runs in CI
- PRs fail if quality drops
- Scores visible in CI logs

---

### G7: Dashboard Metrics
**Status**: Not Started
**Estimated**: 3 hours
**Dependencies**: G1

- [ ] Create metrics endpoint
- [ ] Track per-twin metrics:
  - Total chats
  - Avg confidence
  - Escalation rate
  - Memory growth
- [ ] Display on dashboard

**Metrics Schema**:
```python
class TwinMetrics(BaseModel):
    total_conversations: int
    total_messages: int
    avg_confidence: float
    escalation_count: int
    escalation_rate: float
    memory_candidates_pending: int
    memory_candidates_approved: int
    graph_nodes_count: int
    documents_count: int
```

**Acceptance Criteria**:
- Metrics calculated correctly
- Visible on twin dashboard
- Updates in real-time

---

### G8: Error Tracking
**Status**: Not Started
**Estimated**: 2 hours
**Dependencies**: G1

- [ ] Log errors to Langfuse
- [ ] Track error types:
  - LLM failures
  - Retrieval failures
  - Database errors
- [ ] Alert on error rate threshold

**Error Logging**:
```python
try:
    response = await generate_response(...)
except OpenAIError as e:
    langfuse.log_error(
        exception=e,
        context={"twin_id": twin_id, "query": query}
    )
    raise
```

**Acceptance Criteria**:
- Errors visible in Langfuse
- Error types categorized
- Can diagnose issues quickly

---

## Progress

| Task | Status | Date | Notes |
|------|--------|------|-------|
| G1 | Not Started | | |
| G2 | Not Started | | |
| G3 | Not Started | | |
| G4 | Not Started | | |
| G5 | Not Started | | |
| G6 | Not Started | | |
| G7 | Not Started | | |
| G8 | Not Started | | |
