"""
Conversational Query Rewriting Module

Transforms underspecified chat queries into standalone retrieval queries
using conversation history for context resolution.

Based on research:
- RECAP: REwriting Conversations for Agent Planning (Megagon Labs, 2025)
- DMQR-RAG: Diverse Multi-Query Rewriting (Kuaishou, 2024)
- CHIQ: Contextual History enhancement for Intent Understanding (2024)
"""

import os
import re
import json
import asyncio
import hashlib
import time
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache
from pydantic import BaseModel, Field
from datetime import datetime

from modules.clients import get_openai_client
from modules.langfuse_sdk import observe, langfuse_context

# Try to import metrics collector
try:
    from modules.metrics_collector import get_metrics_collector
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

# Configuration
QUERY_REWRITING_ENABLED = os.getenv("QUERY_REWRITING_ENABLED", "false").lower() == "true"

# LLM Model Selection - Using Latest OpenAI Models
# Available options (latest to older):
#   - "gpt-4o"          : Latest flagship (best quality, ~2x cost of mini)
#   - "gpt-4o-mini"     : Fast & cost-effective (recommended for production)
#   - "o1-preview"      : Reasoning model (slower, overkill for query rewriting)
#   - "o1-mini"         : Faster reasoning (still slower than 4o)
# Note: GPT-5 has not been released yet (as of Feb 2026)
QUERY_REWRITING_MODEL = os.getenv("QUERY_REWRITING_MODEL", "gpt-4o")

QUERY_REWRITING_MAX_HISTORY = int(os.getenv("QUERY_REWRITING_MAX_HISTORY", "5"))
QUERY_REWRITING_MIN_CONFIDENCE = float(os.getenv("QUERY_REWRITING_MIN_CONFIDENCE", "0.7"))
QUERY_REWRITING_TIMEOUT = float(os.getenv("QUERY_REWRITING_TIMEOUT", "3.0"))

# Caching Configuration
QUERY_REWRITE_CACHE_ENABLED = os.getenv("QUERY_REWRITE_CACHE_ENABLED", "true").lower() == "true"
QUERY_REWRITE_CACHE_SIZE = int(os.getenv("QUERY_REWRITE_CACHE_SIZE", "1000"))
QUERY_REWRITE_CACHE_TTL_SECONDS = float(os.getenv("QUERY_REWRITE_CACHE_TTL_SECONDS", "300"))  # 5 minutes

# A/B Testing Configuration
QUERY_REWRITE_AB_TEST_ENABLED = os.getenv("QUERY_REWRITE_AB_TEST_ENABLED", "false").lower() == "true"
QUERY_REWRITE_ROLLOUT_PERCENT = float(os.getenv("QUERY_REWRITE_ROLLOUT_PERCENT", "0"))  # 0-100

# Common pronouns and references to resolve
PRONOUN_PATTERNS = {
    "it": r"\bit\b",
    "that": r"\bthat\b",
    "this": r"\bthis\b",
    "they": r"\bthey\b",
    "them": r"\bthem\b",
    "their": r"\btheir\b",
    "these": r"\bthese\b",
    "those": r"\bthose\b",
}

INTENT_CATEGORIES = [
    "factual_lookup",      # "What is X?"
    "comparison",          # "How does X compare to Y?"
    "temporal_analysis",   # "What changed since X?"
    "procedural",          # "How do I do X?"
    "elaboration",         # "Tell me more about X"
    "clarification",       # "Do you mean X or Y?"
    "follow_up",           # "What about Y?"
    "aggregation",         # "Sum up all X"
    "causal_analysis",     # "Why did X happen?"
    "counterfactual",      # "What if X had happened?"
]


class QueryRewriteResult(BaseModel):
    """Result of conversational query rewriting."""
    
    standalone_query: str = Field(description="The rewritten standalone query")
    original_query: str = Field(description="Original user query")
    intent: str = Field(default="unknown", description="Classified intent")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Suggested filters")
    requires_history: bool = Field(default=False, description="Whether history was needed")
    rewrite_applied: bool = Field(default=False, description="Whether rewrite differs from original")
    rewrite_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(default="", description="Reasoning for the rewrite")
    latency_ms: float = Field(default=0.0, description="Processing time in milliseconds")
    from_cache: bool = Field(default=False, description="Whether result was from cache")


class QueryRewriteCache:
    """Simple TTL cache for query rewrites."""
    
    def __init__(self, maxsize: int = 1000, ttl_seconds: float = 300):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[QueryRewriteResult, float]] = {}
    
    def _make_key(self, query: str, history: List[Dict[str, str]]) -> str:
        """Create cache key from query and history."""
        # Normalize for caching
        history_str = json.dumps(history, sort_keys=True, ensure_ascii=True)
        key_str = f"{query.lower().strip()}:{history_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, query: str, history: List[Dict[str, str]]) -> Optional[QueryRewriteResult]:
        """Get cached result if not expired."""
        if not QUERY_REWRITE_CACHE_ENABLED:
            return None
        
        key = self._make_key(query, history)
        if key in self._cache:
            result, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                # Return copy with cache flag
                cached_result = result.copy()
                cached_result.from_cache = True
                return cached_result
            else:
                # Expired
                del self._cache[key]
        return None
    
    def set(self, query: str, history: List[Dict[str, str]], result: QueryRewriteResult):
        """Cache a result."""
        if not QUERY_REWRITE_CACHE_ENABLED:
            return
        
        # Evict oldest if at capacity (simple FIFO)
        if len(self._cache) >= self.maxsize:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        key = self._make_key(query, history)
        self._cache[key] = (result, time.time())
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
        }


# Global cache instance
_query_rewrite_cache = QueryRewriteCache(
    maxsize=QUERY_REWRITE_CACHE_SIZE,
    ttl_seconds=QUERY_REWRITE_CACHE_TTL_SECONDS,
)


class ConversationalQueryRewriter:
    """
    Rewrites conversational queries into standalone retrieval queries.
    
    Handles:
    - Pronoun resolution ("it", "that", "this")
    - Entity carry-over from history
    - Intent classification
    - Context enhancement
    """
    
    def __init__(
        self,
        max_history_turns: int = QUERY_REWRITING_MAX_HISTORY,
        min_confidence: float = QUERY_REWRITING_MIN_CONFIDENCE,
        model: str = QUERY_REWRITING_MODEL,
    ):
        self.max_history_turns = max_history_turns
        self.min_confidence = min_confidence
        self.model = model
        self._llm_client = None
    
    def _get_llm_client(self):
        """Lazy initialization of LLM client."""
        if self._llm_client is None:
            self._llm_client = get_openai_client()
        return self._llm_client
    
    @observe(name="query_rewrite")
    async def rewrite(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        twin_context: Optional[Dict[str, Any]] = None,
    ) -> QueryRewriteResult:
        """
        Rewrite a conversational query into a standalone retrieval query.
        
        Args:
            current_query: The current user query (possibly underspecified)
            conversation_history: List of {role, content} message dicts
            twin_context: Optional twin-specific context (name, domain, etc.)
            
        Returns:
            QueryRewriteResult with standalone query and metadata
        """
        start_time = datetime.utcnow()
        
        # Check cache first
        cached = _query_rewrite_cache.get(current_query, conversation_history)
        if cached:
            print(f"[QueryRewrite] Cache hit for '{current_query[:50]}...'")
            cached.latency_ms = 0.0  # Reset latency for cached result
            self._log_metrics(cached, cached=True)
            return cached
        
        # Fast path: standalone queries don't need rewriting
        if self._is_standalone_query(current_query):
            result = QueryRewriteResult(
                standalone_query=current_query,
                original_query=current_query,
                intent="standalone",
                requires_history=False,
                rewrite_applied=False,
                rewrite_confidence=1.0,
                reasoning="Query is already standalone",
                latency_ms=0.0,
            )
        
        # Step 1: Rule-based pronoun resolution (fast)
        rule_based = self._resolve_pronouns_rule_based(
            current_query, conversation_history
        )
        
        # Step 2: LLM-based rewriting with full context
        try:
            llm_result = await self._rewrite_with_llm(
                current_query=current_query,
                conversation_history=conversation_history,
                twin_context=twin_context,
                rule_based_hint=rule_based,
            )
        except Exception as e:
            print(f"[QueryRewriter] LLM rewrite failed: {e}")
            # Fallback to rule-based
            llm_result = QueryRewriteResult(
                standalone_query=rule_based,
                original_query=current_query,
                intent="unknown",
                requires_history=True,
                rewrite_applied=rule_based != current_query,
                rewrite_confidence=0.5,
                reasoning="LLM failed, using rule-based fallback",
            )
        
        # Calculate latency
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        llm_result.latency_ms = latency_ms
        
        # Apply confidence threshold
        if llm_result.rewrite_confidence < self.min_confidence:
            print(f"[QueryRewriter] Confidence {llm_result.rewrite_confidence:.2f} below threshold, using original")
            llm_result.standalone_query = current_query
            llm_result.rewrite_applied = False
            llm_result.reasoning += " (confidence too low, using original)"
        
        # Cache the result
        if llm_result.rewrite_applied:
            _query_rewrite_cache.set(current_query, conversation_history, llm_result)
        
        # Log metrics
        self._log_metrics(llm_result, cached=False)
        
        return llm_result
    
    def _log_metrics(self, result: QueryRewriteResult, cached: bool = False):
        """Log metrics for observability."""
        try:
            # Log to Langfuse if available
            if hasattr(langfuse_context, 'update_current_observation'):
                langfuse_context.update_current_observation(
                    metadata={
                        "query_rewrite.original": result.original_query[:100],
                        "query_rewrite.rewritten": result.standalone_query[:100],
                        "query_rewrite.intent": result.intent,
                        "query_rewrite.confidence": result.rewrite_confidence,
                        "query_rewrite.applied": result.rewrite_applied,
                        "query_rewrite.cached": cached,
                        "query_rewrite.latency_ms": result.latency_ms,
                    }
                )
            
            # Log to metrics collector if available
            if METRICS_AVAILABLE:
                metrics = get_metrics_collector()
                if metrics:
                    # Use safe method calls with fallbacks
                    try:
                        if hasattr(metrics, 'increment_counter'):
                            metrics.increment_counter("query_rewrite.total")
                            if result.rewrite_applied:
                                metrics.increment_counter("query_rewrite.applied")
                            if cached:
                                metrics.increment_counter("query_rewrite.cache_hit")
                    except Exception:
                        pass
                    
                    try:
                        if hasattr(metrics, 'record_histogram'):
                            metrics.record_histogram("query_rewrite.confidence", result.rewrite_confidence)
                            metrics.record_histogram("query_rewrite.latency_ms", result.latency_ms)
                    except Exception:
                        pass
        except Exception as e:
            # Don't fail on metrics logging
            print(f"[QueryRewrite] Metrics logging failed: {e}")
    
    def _is_standalone_query(self, query: str) -> bool:
        """
        Check if a query is already standalone (doesn't need rewriting).
        
        Heuristics:
        - No pronouns or references
        - Contains specific entities
        - Sufficient length
        """
        query_lower = query.lower()
        
        # Check for pronouns
        for pronoun, pattern in PRONOUN_PATTERNS.items():
            if re.search(pattern, query_lower):
                return False
        
        # Check for vague terms
        vague_terms = ["what about", "how about", "and ", "is it", "are they"]
        for term in vague_terms:
            if query_lower.startswith(term) or f" {term}" in query_lower:
                return False
        
        # Check for sufficient specificity (length-based heuristic)
        if len(query.split()) < 3:
            return False
        
        return True
    
    def _resolve_pronouns_rule_based(
        self,
        query: str,
        history: List[Dict[str, str]],
    ) -> str:
        """
        Fast rule-based pronoun resolution.
        
        Strategy:
        1. Extract last mentioned entity from history
        2. Replace pronouns with that entity
        """
        if not history:
            return query
        
        # Extract nouns/topics from recent assistant responses
        last_entities = self._extract_entities_from_history(history[-3:])
        
        if not last_entities:
            return query
        
        primary_entity = last_entities[0] if last_entities else None
        query_lower = query.lower()
        
        # Replace pronouns
        resolved = query
        if primary_entity:
            # Replace "it" with entity (if context suggests singular noun)
            if re.search(r"\bit\b", query_lower):
                resolved = re.sub(r"\bit\b", primary_entity, resolved, flags=re.IGNORECASE)
            
            # Replace "that" with "that {entity}"
            if re.search(r"\bthat\b", query_lower):
                resolved = re.sub(
                    r"\bthat\b",
                    f"that {primary_entity}",
                    resolved,
                    flags=re.IGNORECASE,
                    count=1
                )
            
            # Replace "this" with "this {entity}"
            if re.search(r"\bthis\b", query_lower):
                resolved = re.sub(
                    r"\bthis\b",
                    f"this {primary_entity}",
                    resolved,
                    flags=re.IGNORECASE,
                    count=1
                )
        
        return resolved
    
    def _extract_entities_from_history(
        self,
        history: List[Dict[str, str]],
    ) -> List[str]:
        """
        Extract key entities (nouns, topics) from conversation history.
        
        Uses multiple heuristics:
        1. Quoted terms
        2. Capitalized proper nouns (but filter out common words)
        3. Key business terms
        4. Numbers with units (e.g., "$5.2M", "15%")
        """
        entities = []
        common_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was',
            'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new',
            'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'she', 'use', 'her', 'way', 'many',
            'oil', 'sit', 'set', 'run', 'eat', 'far', 'sea', 'eye', 'ago', 'off', 'too', 'any',
            'say', 'man', 'try', 'ask', 'end', 'why', 'let', 'put', 'say', 'she', 'try', 'way',
            'own', 'say', 'too', 'old', 'tell', 'show', 'give', 'what', 'when', 'make', 'like',
            'time', 'very', 'after', 'back', 'other', 'many', 'than', 'then', 'them', 'well',
            'about', 'could', 'would', 'there', 'their', 'where', 'being', 'every', 'great',
            'might', 'shall', 'still', 'those', 'which', 'would', 'this', 'that', 'with',
            'from', 'have', 'were', 'said', 'word', 'been', 'find', 'long', 'down', 'come',
            'made', 'part', 'over', 'know', 'take', 'year', 'good', 'only', 'just', 'name',
        }
        
        for msg in reversed(history):
            content = msg.get("content", "")
            
            # Extract quoted terms (high priority)
            quoted = re.findall(r'"([^"]{3,50})"', content)
            entities.extend(quoted)
            
            # Extract monetary amounts
            money = re.findall(r'\$[\d,]+(?:\.\d+)?[MK]?|\d+\s*(?:million|billion|dollars?)', content, re.IGNORECASE)
            entities.extend(money)
            
            # Extract percentages
            percentages = re.findall(r'\d+(?:\.\d+)?%', content)
            entities.extend(percentages)
            
            # Extract time periods
            time_periods = re.findall(r'\bQ[1-4][\s\-\']?(?:\d{2}|\d{4})?\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}?\b|\b\d{4}\b', content, re.IGNORECASE)
            entities.extend(time_periods)
            
            # Extract capitalized phrases (potential proper nouns)
            # Require at least one word with 4+ characters (to filter out "The", "And", etc)
            capitalized = re.findall(r'\b[A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,})*\b', content)
            for cap in capitalized:
                # Skip if all words are common
                words = cap.lower().split()
                if not all(w in common_words for w in words):
                    # Skip single words that are common
                    if len(words) > 1 or words[0] not in common_words:
                        entities.append(cap)
            
            # Extract business/technical terms (words followed by specific patterns)
            # e.g., "revenue was", "growth rate", "user acquisition"
            business_patterns = re.findall(
                r'\b(revenue|profit|growth|users?|customers?|sales|metrics?|kpis?|'
                r'product|feature|launch|roadmap|strategy|market|competition|'
                r'pricing|cost|budget|forecast|projections?)\s+(?:was|is|are|were|of|for)\b',
                content, re.IGNORECASE
            )
            entities.extend([p[0] for p in business_patterns if isinstance(p, tuple)] or business_patterns)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for e in entities:
            e_lower = e.lower()
            if e_lower not in seen and len(e) > 2:
                seen.add(e_lower)
                unique_entities.append(e)
        
        return unique_entities[:5]  # Return top 5
    
    async def _rewrite_with_llm(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        twin_context: Optional[Dict[str, Any]],
        rule_based_hint: str,
    ) -> QueryRewriteResult:
        """
        Use LLM to perform sophisticated query rewriting.
        """
        # Build prompt
        prompt = self._build_rewrite_prompt(
            current_query=current_query,
            conversation_history=conversation_history,
            twin_context=twin_context,
            rule_based_hint=rule_based_hint,
        )
        
        # Call LLM
        client = self._get_llm_client()
        loop = asyncio.get_event_loop()
        
        def _call_llm():
            return client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at query rewriting for conversational RAG systems."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,  # Low temp for consistency
                response_format={"type": "json_object"},
                timeout=QUERY_REWRITING_TIMEOUT,
            )
        
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _call_llm),
            timeout=QUERY_REWRITING_TIMEOUT + 1.0
        )
        
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        # Extract standalone query
        standalone = parsed.get("standalone_query", rule_based_hint)
        
        # If LLM returns empty or identical, use rule-based
        if not standalone or standalone == current_query:
            standalone = rule_based_hint
        
        return QueryRewriteResult(
            standalone_query=standalone,
            original_query=current_query,
            intent=parsed.get("intent", "unknown"),
            entities=parsed.get("entities", {}),
            filters=parsed.get("filters", {}),
            requires_history=True,
            rewrite_applied=standalone != current_query,
            rewrite_confidence=parsed.get("confidence", 0.7),
            reasoning=parsed.get("reasoning", ""),
        )
    
    def _build_rewrite_prompt(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        twin_context: Optional[Dict[str, Any]],
        rule_based_hint: str,
    ) -> str:
        """Build the prompt for LLM-based query rewriting."""
        
        # Format conversation history
        history_str = ""
        if conversation_history:
            # Take last N turns
            recent = conversation_history[-self.max_history_turns:]
            for msg in recent:
                role = msg.get("role", "user").capitalize()
                content = msg.get("content", "")
                history_str += f"{role}: {content}\n"
        
        # Twin context
        twin_info = ""
        if twin_context:
            twin_name = twin_context.get("name", "the subject")
            twin_domain = twin_context.get("domain", "")
            twin_info = f"\nTWIN CONTEXT:\nName: {twin_name}"
            if twin_domain:
                twin_info += f"\nDomain: {twin_domain}"
        
        prompt = f"""Rewrite the CURRENT QUERY into a standalone search query that can be understood without conversation context.

CONVERSATION HISTORY:
{history_str}
{twin_info}

CURRENT QUERY: {current_query}

RULE-BASED HINT: {rule_based_hint}

TASK:
1. Resolve all pronouns (it, that, this, they) using conversation context
2. Expand acronyms if clear from context
3. Include implicit constraints (timeframe, scope)
4. Make the query specific and searchable

OUTPUT FORMAT (JSON):
{{
  "standalone_query": "the rewritten standalone query",
  "intent": "one of: factual_lookup, comparison, temporal_analysis, procedural, elaboration, clarification, follow_up, aggregation, causal_analysis",
  "entities": {{
    "primary": "main entity",
    "secondary": ["other entities"],
    "timeframe": "if any"
  }},
  "filters": {{
    "suggested_types": ["document types that might help"]
  }},
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of changes made"
}}

EXAMPLES:

Example 1:
History: User: "What's our Q3 revenue?" Assistant: "Q3 revenue was $5.2M, up 15% YoY"
Current: "What about Q4?"
Output: {{
  "standalone_query": "What was the Q4 revenue?",
  "intent": "follow_up",
  "entities": {{"primary": "revenue", "timeframe": "Q4"}},
  "confidence": 0.95,
  "reasoning": "Carried over 'revenue' entity from Q3 mention"
}}

Example 2:
History: User: "Show me the roadmap" Assistant: "Here are the planned features..."
Current: "When is feature X shipping?"
Output: {{
  "standalone_query": "When is feature X shipping according to the roadmap?",
  "intent": "temporal_analysis",
  "entities": {{"primary": "feature X", "source": "roadmap"}},
  "confidence": 0.88,
  "reasoning": "Added 'roadmap' context from history"
}}

Now rewrite the CURRENT QUERY above."""
        
        return prompt
    
    async def rewrite_multi_strategy(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        twin_context: Optional[Dict[str, Any]] = None,
    ) -> List[QueryRewriteResult]:
        """
        Generate multiple rewrites using different strategies (DMQR-RAG approach).
        
        Strategies:
        1. Minimal: Core keywords only
        2. Standard: Expanded with synonyms
        3. Detailed: With constraints and context
        4. Comprehensive: Full context + inference
        
        Returns list of rewrite results for retrieval fusion.
        """
        strategies = ["minimal", "standard", "detailed"]
        
        tasks = [
            self._rewrite_with_strategy(
                current_query, conversation_history, twin_context, s
            )
            for s in strategies
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for r in results:
            if isinstance(r, QueryRewriteResult):
                valid_results.append(r)
            elif isinstance(r, Exception):
                print(f"[QueryRewriter] Strategy failed: {r}")
        
        return valid_results
    
    async def _rewrite_with_strategy(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        twin_context: Optional[Dict[str, Any]],
        strategy: str,
    ) -> QueryRewriteResult:
        """Rewrite using a specific strategy."""
        
        base_result = await self.rewrite(
            current_query, conversation_history, twin_context
        )
        
        if strategy == "minimal":
            # Extract just keywords
            base_result.standalone_query = self._extract_keywords(
                base_result.standalone_query
            )
        elif strategy == "detailed":
            # Add more context
            base_result.standalone_query = self._add_detailed_context(
                base_result.standalone_query,
                conversation_history
            )
        
        return base_result
    
    def _extract_keywords(self, query: str) -> str:
        """Extract core keywords from query."""
        # Simple implementation: remove stopwords
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been"}
        words = query.split()
        keywords = [w for w in words if w.lower() not in stopwords]
        return " ".join(keywords)
    
    def _add_detailed_context(self, query: str, history: List[Dict]) -> str:
        """Add more detailed context from history."""
        # This is a placeholder - could use summarization
        return query


# Convenience function for direct use
async def rewrite_conversational_query(
    current_query: str,
    conversation_history: List[Dict[str, str]],
    twin_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> QueryRewriteResult:
    """
    Convenience function to rewrite a conversational query.
    
    Args:
        current_query: Current user query
        conversation_history: List of {role, content} dicts
        twin_context: Optional twin context
        user_id: Optional user ID for A/B testing assignment
        
    Returns:
        QueryRewriteResult
    """
    if not QUERY_REWRITING_ENABLED:
        return QueryRewriteResult(
            standalone_query=current_query,
            original_query=current_query,
            rewrite_applied=False,
            reasoning="Query rewriting disabled",
        )
    
    # A/B Testing: Check if user should get rewritten queries
    if QUERY_REWRITE_AB_TEST_ENABLED and user_id:
        # Deterministic assignment based on user_id
        import hashlib
        user_hash = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
        user_bucket = user_hash % 100
        
        if user_bucket >= QUERY_REWRITE_ROLLOUT_PERCENT:
            # User in control group - skip rewriting
            return QueryRewriteResult(
                standalone_query=current_query,
                original_query=current_query,
                rewrite_applied=False,
                reasoning=f"A/B test control group (bucket: {user_bucket})",
            )
    
    rewriter = ConversationalQueryRewriter()
    return await rewriter.rewrite(current_query, conversation_history, twin_context)


def get_query_rewrite_stats() -> Dict[str, Any]:
    """Get query rewriting statistics."""
    return {
        "enabled": QUERY_REWRITING_ENABLED,
        "cache": _query_rewrite_cache.get_stats(),
        "ab_test": {
            "enabled": QUERY_REWRITE_AB_TEST_ENABLED,
            "rollout_percent": QUERY_REWRITE_ROLLOUT_PERCENT,
        },
        "config": {
            "model": QUERY_REWRITING_MODEL,
            "max_history": QUERY_REWRITING_MAX_HISTORY,
            "min_confidence": QUERY_REWRITING_MIN_CONFIDENCE,
            "timeout": QUERY_REWRITING_TIMEOUT,
        },
    }


# For testing
if __name__ == "__main__":
    async def test():
        rewriter = ConversationalQueryRewriter()
        
        # Test case 1: Follow-up
        history = [
            {"role": "user", "content": "What's our Q3 revenue?"},
            {"role": "assistant", "content": "Q3 revenue was $5.2M, up 15% year over year."}
        ]
        result = await rewriter.rewrite("What about Q4?", history)
        print(f"Test 1 - Follow-up:")
        print(f"  Original: What about Q4?")
        print(f"  Rewritten: {result.standalone_query}")
        print(f"  Intent: {result.intent}")
        print(f"  Confidence: {result.rewrite_confidence}")
        print()
        
        # Test case 2: Standalone (should not rewrite)
        result2 = await rewriter.rewrite(
            "What is the company's mission statement?",
            []
        )
        print(f"Test 2 - Standalone:")
        print(f"  Original: What is the company's mission statement?")
        print(f"  Rewritten: {result2.standalone_query}")
        print(f"  Applied: {result2.rewrite_applied}")
    
    asyncio.run(test())
