"""
retrieval_intent.py

Phase 1: Intent Classification for Smart Retrieval
Classifies user queries to determine optimal retrieval strategy.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from modules.inference_router import get_openai_client


class RetrievalIntentType(str, Enum):
    """Types of retrieval intents."""
    ENTITY_LOOKUP = "entity_lookup"           # "What is X?", "Tell me about Y"
    SUMMARIZATION = "summarization"           # "Summarize your experience"
    COMPARISON = "comparison"                 # "Compare X and Y", "X vs Y"
    OPINION = "opinion"                       # "What do you think?", "Your view?"
    PROCEDURAL = "procedural"                 # "How do you do X?", "Steps for Y"
    TEMPORAL = "temporal"                     # "What happened in 2023?"
    CAUSAL = "causal"                         # "Why did X happen?", "Reasons for Y"
    SOCIAL = "social"                         # "Who do you know?", "Your network"
    CLARIFICATION = "clarification"           # "What do you mean?"
    GREETING = "greeting"                     # "Hello", "Hi"
    FOLLOWUP = "followup"                     # "What about that?", "Tell me more"
    GENERAL = "general"                       # Catch-all


@dataclass
class RetrievalIntent:
    """Structured intent classification result."""
    intent_type: RetrievalIntentType
    confidence: float
    key_entities: List[str]
    temporal_references: List[str]
    implied_question: str
    is_followup: bool
    retrieval_strategy: str
    metadata_filters: Optional[Dict[str, Any]] = None
    requires_expansion: bool = True


INTENT_CLASSIFICATION_PROMPT = """You are a query intent classifier for a Digital Twin RAG system.

Analyze the user query and conversation history to determine:
1. What type of information the user is seeking
2. Key entities mentioned
3. Whether this is a follow-up question
4. The implied complete question (resolve "it", "that", "this")

Query: "{query}"

Conversation History (last 3 messages):
{history}

Classify into ONE of these intent types:
- entity_lookup: Seeking specific info about something ("What is X?", "Tell me about Y")
- summarization: Asking for overview/summary ("Summarize", "Give me an overview")
- comparison: Comparing two+ things ("Compare X and Y", "X vs Y", "difference between")
- opinion: Asking for views/opinions ("What do you think?", "Your view on X?")
- procedural: How-to/step-by-step ("How do you", "Steps to", "Process for")
- temporal: Time-specific ("When", "In 2023", "Last year", "Recently")
- causal: Why/explanation ("Why", "Reasons for", "Cause of")
- social: Relationships/network ("Who do you know", "Your connections")
- clarification: Asking for explanation of previous ("What do you mean")
- greeting: Simple greeting ("Hello", "Hi", "Hey")
- followup: Referencing previous context ("What about that", "Tell me more")
- general: Other queries

Return JSON:
{{
  "intent_type": "entity_lookup",
  "confidence": 0.92,
  "key_entities": ["entity1", "entity2"],
  "temporal_references": ["2023", "last year"],
  "implied_question": "What is the definition of X?",
  "is_followup": false,
  "retrieval_strategy": "direct_vector_with_expansion",
  "metadata_filters": {{"category": "FACT"}},
  "requires_expansion": true
}}

Rules:
- is_followup: true if query references previous conversation ("it", "that", "this", "they")
- implied_question: Rewrite query as standalone if it's a followup
- metadata_filters: Use for opinion queries ({{"category": "OPINION"}}) or specific types
- requires_expansion: true for complex queries, false for simple entity lookups
"""


async def classify_retrieval_intent(
    query: str,
    history: Optional[List[Dict[str, Any]]] = None
) -> RetrievalIntent:
    """
    Classify the retrieval intent of a user query.
    
    Args:
        query: User query string
        history: Optional conversation history (last N messages)
        
    Returns:
        RetrievalIntent with classification results
    """
    if not query or not query.strip():
        return RetrievalIntent(
            intent_type=RetrievalIntentType.GENERAL,
            confidence=0.0,
            key_entities=[],
            temporal_references=[],
            implied_question="",
            is_followup=False,
            retrieval_strategy="direct_vector"
        )
    
    # Format history for prompt
    history_str = "None"
    if history:
        # Take last 3 messages, format simply
        recent = history[-3:] if len(history) > 3 else history
        history_lines = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:150]  # Truncate long messages
            history_lines.append(f"{role}: {content}")
        history_str = "\n".join(history_lines) if history_lines else "None"
    
    client = get_openai_client()
    
    try:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            query=query.strip(),
            history=history_str
        )
        
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.1  # Low temp for consistent classification
            ),
            timeout=2.0  # 2 second timeout
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Parse and validate
        intent_type = RetrievalIntentType(
            result.get("intent_type", "general")
        )
        
        return RetrievalIntent(
            intent_type=intent_type,
            confidence=float(result.get("confidence", 0.5)),
            key_entities=result.get("key_entities", []),
            temporal_references=result.get("temporal_references", []),
            implied_question=result.get("implied_question", query),
            is_followup=bool(result.get("is_followup", False)),
            retrieval_strategy=result.get("retrieval_strategy", "direct_vector"),
            metadata_filters=result.get("metadata_filters"),
            requires_expansion=bool(result.get("requires_expansion", True))
        )
        
    except asyncio.TimeoutError:
        print(f"[Intent Classification] Timeout for query: {query[:50]}...")
        # Fallback: simple heuristic classification
        return _heuristic_intent_classification(query)
        
    except Exception as e:
        print(f"[Intent Classification] Error: {e}")
        # Fallback to heuristic
        return _heuristic_intent_classification(query)


def _heuristic_intent_classification(query: str) -> RetrievalIntent:
    """Fast heuristic classification when LLM fails."""
    q_lower = query.lower()
    
    # Simple keyword matching
    if any(word in q_lower for word in ["hello", "hi", "hey", "greetings"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.GREETING,
            confidence=0.8,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="no_retrieval"
        )
    
    if any(word in q_lower for word in ["compare", "versus", "vs", "difference between"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.COMPARISON,
            confidence=0.7,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="multi_entity_retrieval"
        )
    
    if any(word in q_lower for word in ["what do you think", "your opinion", "your view"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.OPINION,
            confidence=0.8,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="opinion_filtered",
            metadata_filters={"category": "OPINION"}
        )
    
    if any(word in q_lower for word in ["how do you", "steps to", "process", "procedure"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.PROCEDURAL,
            confidence=0.7,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="sequential_chunk_retrieval"
        )
    
    if any(word in q_lower for word in ["why", "reason", "cause"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.CAUSAL,
            confidence=0.6,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="explanation_focused"
        )
    
    if any(word in q_lower for word in ["summarize", "overview", "summary"]):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.SUMMARIZATION,
            confidence=0.7,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=False,
            retrieval_strategy="broad_retrieval"
        )
    
    # Check for followup indicators
    followup_indicators = ["it", "that", "this", "they", "them", "those"]
    if any(word in q_lower.split() for word in followup_indicators):
        return RetrievalIntent(
            intent_type=RetrievalIntentType.FOLLOWUP,
            confidence=0.6,
            key_entities=[],
            temporal_references=[],
            implied_question=query,
            is_followup=True,
            retrieval_strategy="context_aware"
        )
    
    # Default: entity lookup
    return RetrievalIntent(
        intent_type=RetrievalIntentType.ENTITY_LOOKUP,
        confidence=0.5,
        key_entities=[],
        temporal_references=[],
        implied_question=query,
        is_followup=False,
        retrieval_strategy="direct_vector_with_expansion"
    )


# Strategy mapping
STRATEGY_CONFIG = {
    "entity_lookup": {
        "top_k": 5,
        "use_hyde": True,
        "use_expansion": True,
    },
    "summarization": {
        "top_k": 15,
        "use_hyde": False,
        "use_expansion": True,
        "aggregate": True,
    },
    "comparison": {
        "top_k": 10,
        "use_hyde": False,
        "use_expansion": True,
        "per_entity_k": 5,
    },
    "opinion": {
        "top_k": 8,
        "use_hyde": True,
        "use_expansion": True,
        "metadata_filter": {"category": "OPINION"},
    },
    "procedural": {
        "top_k": 10,
        "use_hyde": False,
        "use_expansion": True,
        "prefer_sequential": True,
    },
    "temporal": {
        "top_k": 8,
        "use_hyde": False,
        "use_expansion": False,
        "time_sensitive": True,
    },
    "causal": {
        "top_k": 8,
        "use_hyde": True,
        "use_expansion": True,
    },
    "social": {
        "top_k": 6,
        "use_hyde": False,
        "use_expansion": True,
    },
    "greeting": {
        "top_k": 0,  # No retrieval
        "skip_retrieval": True,
    },
    "followup": {
        "top_k": 8,
        "use_hyde": False,
        "use_expansion": True,
        "use_conversation_context": True,
    },
    "general": {
        "top_k": 5,
        "use_hyde": True,
        "use_expansion": True,
    }
}


def get_strategy_config(intent_type: RetrievalIntentType) -> Dict[str, Any]:
    """Get retrieval configuration for an intent type."""
    return STRATEGY_CONFIG.get(intent_type.value, STRATEGY_CONFIG["general"])
