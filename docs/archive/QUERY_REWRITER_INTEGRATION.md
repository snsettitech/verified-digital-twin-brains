# Query Rewriter Integration Guide

This document shows how to integrate the conversational query rewriter into the existing agent pipeline.

## Integration Points

### Option 1: Integration in `router_node` (Recommended)

**File:** `backend/modules/agent.py`
**Location:** Inside `router_node` function (line ~653)

```python
# Add import at top of file
from modules.query_rewriter import (
    ConversationalQueryRewriter,
    QueryRewriteResult,
    QUERY_REWRITING_ENABLED,
)

# Add to router_node
@observe(name="router_node")
async def router_node(state: TwinState):
    """
    Generalized router for document reasoning with query rewriting.
    """
    messages = state["messages"]
    user_query = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    # NEW: Conversational query rewriting
    effective_query = user_query
    rewrite_result: Optional[QueryRewriteResult] = None
    
    if QUERY_REWRITING_ENABLED:
        try:
            # Extract conversation history from messages
            conversation_history = _extract_conversation_history(messages, max_turns=5)
            
            rewriter = ConversationalQueryRewriter()
            rewrite_result = await rewriter.rewrite(
                current_query=user_query,
                conversation_history=conversation_history,
                twin_context={
                    "twin_id": state.get("twin_id"),
                    "name": state.get("twin_name"),  # if available
                }
            )
            
            effective_query = rewrite_result.standalone_query
            
            # Log rewrite for observability
            print(f"[Router] Query rewritten: '{user_query}' -> '{effective_query}'")
            
        except Exception as e:
            print(f"[Router] Query rewriting failed: {e}")
            effective_query = user_query
    
    # Use effective_query for downstream processing
    interaction_context = (state.get("interaction_context") or "owner_chat").strip().lower()
    twin_id = state.get("twin_id")
    knowledge_available = _twin_has_groundable_knowledge(twin_id)
    
    # Apply grounding policy to rewritten query
    query_policy = get_grounding_policy(effective_query, interaction_context=interaction_context)
    is_smalltalk = bool(query_policy.get("is_smalltalk"))
    
    # ... rest of existing logic
    
    # Include rewrite info in return
    return {
        "dialogue_mode": dialogue_mode,
        "intent_label": intent_label,
        "target_owner_scope": False,
        "requires_evidence": requires_evidence,
        "sub_queries": [effective_query] if requires_evidence else [],
        "original_query": user_query,  # NEW
        "rewritten_query": effective_query,  # NEW
        "query_rewrite_result": rewrite_result.dict() if rewrite_result else None,  # NEW
        # ... rest of return dict
    }


def _extract_conversation_history(
    messages: List[BaseMessage],
    max_turns: int = 5
) -> List[Dict[str, str]]:
    """Extract conversation history from LangChain messages."""
    history = []
    
    # Take last N user-assistant pairs
    recent = messages[-max_turns*2:] if len(messages) > max_turns*2 else messages
    
    for msg in recent:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            history.append({"role": "assistant", "content": msg.content})
    
    return history
```

### Option 2: Integration in Chat Router (Alternative)

**File:** `backend/routers/chat.py`
**Location:** Before calling `run_agent_stream`

```python
# In chat endpoint, before agent execution
from modules.query_rewriter import rewrite_conversational_query

async def chat(...):
    # ... existing code
    
    # Get conversation history
    raw_history = []
    if conversation_id:
        raw_history = get_messages(conversation_id)
    
    # Rewrite query if enabled
    effective_query = query
    if QUERY_REWRITING_ENABLED and raw_history:
        rewrite_result = await rewrite_conversational_query(
            current_query=query,
            conversation_history=[
                {"role": m.get("role"), "content": m.get("content", "")}
                for m in raw_history[-5:]
            ],
            twin_context={"twin_id": twin_id}
        )
        effective_query = rewrite_result.standalone_query
        
        # Store rewrite info for debugging
        context_trace["query_rewrite"] = {
            "original": query,
            "rewritten": effective_query,
            "applied": rewrite_result.rewrite_applied,
            "confidence": rewrite_result.rewrite_confidence,
        }
    
    # Pass effective_query to agent
    # ... rest of chat logic
```

## Environment Variables

Add to `.env` and `render.yaml`:

```bash
# Query Rewriting Configuration
QUERY_REWRITING_ENABLED=true
QUERY_REWRITING_MODEL=gpt-4o-mini
QUERY_REWRITING_MAX_HISTORY=5
QUERY_REWRITING_MIN_CONFIDENCE=0.7
QUERY_REWRITING_TIMEOUT=3.0
```

## Testing

### Unit Tests

```python
# tests/test_query_rewriter.py
import pytest
from modules.query_rewriter import ConversationalQueryRewriter, QueryRewriteResult

@pytest.fixture
def rewriter():
    return ConversationalQueryRewriter()


@pytest.mark.asyncio
async def test_follow_up_rewrite(rewriter):
    """Test follow-up query rewriting."""
    history = [
        {"role": "user", "content": "What's our Q3 revenue?"},
        {"role": "assistant", "content": "Q3 revenue was $5.2M."}
    ]
    
    result = await rewriter.rewrite("What about Q4?", history)
    
    assert "revenue" in result.standalone_query.lower()
    assert "Q4" in result.standalone_query
    assert result.intent == "follow_up"
    assert result.rewrite_applied is True


@pytest.mark.asyncio
async def test_standalone_query_skipped(rewriter):
    """Test that standalone queries are not rewritten."""
    query = "What is the company's mission statement?"
    result = await rewriter.rewrite(query, [])
    
    assert result.standalone_query == query
    assert result.rewrite_applied is False


@pytest.mark.asyncio
async def test_pronoun_resolution(rewriter):
    """Test pronoun resolution."""
    history = [
        {"role": "user", "content": "Tell me about the new product launch."},
        {"role": "assistant", "content": "The product launch is scheduled for next month."}
    ]
    
    result = await rewriter.rewrite("When is it happening?", history)
    
    assert "product launch" in result.standalone_query.lower()


@pytest.mark.asyncio
async def test_low_confidence_fallback(rewriter):
    """Test that low confidence rewrites fall back to original."""
    # Force low confidence
    rewriter.min_confidence = 0.99
    
    history = [{"role": "user", "content": "Something vague"}]
    result = await rewriter.rewrite("What about that?", history)
    
    # Should fallback to original
    assert result.standalone_query == "What about that?"
    assert result.rewrite_applied is False
```

### Integration Tests

```python
# tests/test_query_rewriter_integration.py
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_query_rewriter_in_router():
    """Test query rewriter integration in router_node."""
    from modules.agent import router_node
    
    # Mock state
    state = {
        "messages": [
            HumanMessage(content="What's Q3 revenue?"),
            AIMessage(content="Q3 revenue was $5M"),
            HumanMessage(content="What about Q4?"),
        ],
        "twin_id": "test_twin",
        "interaction_context": "owner_chat",
    }
    
    with patch("modules.agent.QUERY_REWRITING_ENABLED", True):
        result = await router_node(state)
        
        # Check that rewrite happened
        assert "original_query" in result
        assert "rewritten_query" in result
        assert result["original_query"] == "What about Q4?"
        assert "Q4" in result["rewritten_query"]
```

## Monitoring

### Langfuse Traces

Add to `router_node`:

```python
from modules.langfuse_sdk import langfuse_context

# In router_node after rewrite
if rewrite_result and rewrite_result.rewrite_applied:
    langfuse_context.update_current_observation(
        metadata={
            "query_rewrite.original": user_query,
            "query_rewrite.rewritten": effective_query,
            "query_rewrite.intent": rewrite_result.intent,
            "query_rewrite.confidence": rewrite_result.rewrite_confidence,
            "query_rewrite.latency_ms": rewrite_result.latency_ms,
        }
    )
```

### Metrics to Track

```python
# In metrics collection
QUERY_REWRITE_METRICS = {
    "query_rewrite.rate": "% of queries rewritten",
    "query_rewrite.avg_confidence": "Average rewrite confidence",
    "query_rewrite.latency_p99": "P99 latency of rewriting",
    "query_rewrite.fallback_rate": "% falling back to original",
    "retrieval.improvement_with_rewrite": "NDCG@5 improvement",
}
```

## Rollout Strategy

### Phase 1: Shadow Mode (Week 1)

```python
# Log rewrites but don't use them
rewrite_result = await rewriter.rewrite(...)
print(f"[Shadow] Would rewrite: '{user_query}' -> '{rewrite_result.standalone_query}'")
effective_query = user_query  # Still use original
```

### Phase 2: A/B Test (Week 2-3)

```python
import random

# 50% of users get rewriting
use_rewrite = random.random() < 0.5
if use_rewrite and rewrite_result.rewrite_applied:
    effective_query = rewrite_result.standalone_query
```

### Phase 3: Full Rollout (Week 4)

```python
# All users get rewriting
if rewrite_result and rewrite_result.rewrite_applied:
    effective_query = rewrite_result.standalone_query
```

## Troubleshooting

### Issue: High Latency

**Symptoms:** Query rewriting adds 200-500ms latency

**Solutions:**
1. Reduce `QUERY_REWRITING_TIMEOUT` to 2.0s
2. Cache common rewrite patterns
3. Use cheaper model (gpt-4o-mini is already optimal)
4. Skip rewriting for short/simple queries

### Issue: Poor Quality Rewrites

**Symptoms:** Rewrites are incorrect or misleading

**Solutions:**
1. Increase `QUERY_REWRITING_MIN_CONFIDENCE` to 0.8
2. Add more examples to prompt
3. Use multi-strategy approach and ensemble
4. Add human review loop

### Issue: Too Many Fallbacks

**Symptoms:** >50% of queries falling back to original

**Solutions:**
1. Lower `QUERY_REWRITING_MIN_CONFIDENCE` to 0.6
2. Improve entity extraction
3. Add more conversation context

## Performance Optimization

### Caching

```python
from functools import lru_cache
import hashlib

class ConversationalQueryRewriter:
    def __init__(self, ...):
        self._cache = {}
    
    def _get_cache_key(self, query: str, history: List[Dict]) -> str:
        """Generate cache key for query+history pair."""
        history_str = json.dumps(history, sort_keys=True)
        return hashlib.md5(f"{query}:{history_str}".encode()).hexdigest()
    
    async def rewrite(self, query, history, ...):
        cache_key = self._get_cache_key(query, history)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        result = await self._do_rewrite(query, history, ...)
        self._cache[cache_key] = result
        return result
```

### Batch Processing

```python
# For multiple queries
async def rewrite_batch(
    queries: List[str],
    histories: List[List[Dict]],
) -> List[QueryRewriteResult]:
    rewriter = ConversationalQueryRewriter()
    tasks = [
        rewriter.rewrite(q, h)
        for q, h in zip(queries, histories)
    ]
    return await asyncio.gather(*tasks)
```

## Future Enhancements

1. **Fine-tuned Model**: Train a specialized query rewriting model
2. **Multi-language Support**: Handle conversations in different languages
3. **Personalization**: Learn user-specific rewriting patterns
4. **Active Learning**: Collect low-confidence rewrites for improvement
5. **Graph-based**: Use knowledge graph for entity resolution
