"""
conversation_context.py

Phase 2: Conversation Context-Aware Retrieval
Extracts themes, resolves coreferences, and maintains conversation continuity.
"""

import json
import asyncio
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from modules.clients import get_async_openai_client


@dataclass
class ConversationContext:
    """Extracted context from conversation history."""
    themes: List[str]
    current_topic: str
    resolved_entities: Dict[str, str]
    key_entities_mentioned: List[str]
    last_user_question: str
    last_assistant_response: str
    conversation_summary: str
    pronoun_mappings: Dict[str, str]


COREFERENCE_RESOLUTION_PROMPT = """You are a conversation context analyzer.

Given the conversation history and the current query, resolve any ambiguous references.

Conversation History:
{history}

Current Query: "{query}"

Task:
1. Identify what "it", "that", "this", "they", "them" refer to in the current query
2. Extract the main topic of conversation
3. List key entities mentioned so far
4. Rewrite the current query as a standalone question if it has ambiguous references

Return JSON:
{{
  "resolved_query": "The query with all references resolved",
  "current_topic": "Main topic of conversation",
  "themes": ["theme1", "theme2"],
  "key_entities": ["entity1", "entity2"],
  "pronoun_mappings": {{
    "it": "what_it_refers_to",
    "that": "what_that_refers_to"
  }}
}}

Examples:
- "What is Python?" → "Tell me more about it" → resolved: "Tell me more about Python"
- "I like Tesla cars" → "What do you think about them?" → resolved: "What do you think about Tesla cars?"
- "Explain machine learning" → "What are the benefits of that?" → resolved: "What are the benefits of machine learning?"
"""


def format_history_for_prompt(history: List[Dict[str, Any]], max_messages: int = 5) -> str:
    """Format conversation history for prompts."""
    lines = []
    recent = history[-max_messages:] if len(history) > max_messages else history
    
    for msg in recent:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:150]  # Truncate
        lines.append(f"{role}: {content}")
    
    return "\n".join(lines)


def extract_themes_heuristic(history: List[Dict[str, Any]]) -> List[str]:
    """Fast heuristic theme extraction."""
    themes = []
    
    # Extract from recent messages
    for msg in history[-3:]:
        content = msg.get("content", "")
        
        # Find capitalized phrases (potential proper nouns)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        themes.extend(proper_nouns)
        
        # Find technical terms
        tech_terms = re.findall(r'\b[A-Z]{2,}\b|\b[a-z]+_[a-z]+\b', content)
        themes.extend(tech_terms)
    
    # Deduplicate and limit
    seen = set()
    unique_themes = []
    for t in themes:
        t_lower = t.lower()
        if t_lower not in seen and len(t) > 2:
            seen.add(t_lower)
            unique_themes.append(t)
    
    return unique_themes[:5]


def resolve_coreferences_heuristic(query: str, history: List[Dict[str, Any]]) -> str:
    """Fast heuristic coreference resolution."""
    if not history or not query:
        return query
    
    pronouns = ["it", "that", "this", "they", "them", "those", "these"]
    query_lower = query.lower()
    
    # Check if query contains standalone pronouns
    has_pronoun = any(f" {p} " in f" {query_lower} " or f" {p}?" in f" {query_lower}" for p in pronouns)
    if not has_pronoun:
        return query
    
    # Extract key nouns from recent assistant response
    last_topic = ""
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # Simple extraction: first sentence or key phrase
            sentences = content.split('.')
            if sentences:
                last_topic = sentences[0][:100]
            break
    
    # Also check for proper nouns in user messages
    key_entities = []
    for msg in history[-3:]:
        content = msg.get("content", "")
        # Find capitalized words
        caps = re.findall(r'\b[A-Z][a-z]+\b', content)
        key_entities.extend(caps)
    
    # Most common entity
    if key_entities:
        from collections import Counter
        most_common = Counter(key_entities).most_common(1)
        if most_common:
            entity = most_common[0][0]
            # Replace standalone pronouns
            for pronoun in pronouns:
                query = re.sub(rf'\b{pronoun}\b', entity, query, flags=re.IGNORECASE)
            return query
    
    return query


async def resolve_coreferences(
    query: str,
    history: List[Dict[str, Any]]
) -> tuple[str, Dict[str, str]]:
    """
    Resolve pronouns and ambiguous references in the query.
    
    Returns:
        Tuple of (resolved_query, pronoun_mappings)
    """
    if not history or not query:
        return query, {}
    
    # Quick check: does query contain pronouns?
    pronouns = ["it", "that", "this", "they", "them", "those", "these"]
    query_lower = query.lower()
    
    has_pronoun = any(f" {p}" in f" {query_lower}" or f"{p}?" in query_lower for p in pronouns)
    if not has_pronoun:
        return query, {}
    
    # Format history
    history_text = format_history_for_prompt(history[-5:])
    
    client = get_async_openai_client()
    
    try:
        prompt = COREFERENCE_RESOLUTION_PROMPT.format(
            history=history_text,
            query=query
        )
        
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=200,
                temperature=0.1
            ),
            timeout=1.5
        )
        
        result = json.loads(response.choices[0].message.content)
        resolved = result.get("resolved_query", query)
        mappings = result.get("pronoun_mappings", {})
        
        if resolved and resolved != query:
            print(f"[Coreference] '{query}' -> '{resolved}'")
            return resolved, mappings
            
    except asyncio.TimeoutError:
        # Fall back to heuristic
        resolved = resolve_coreferences_heuristic(query, history)
        if resolved != query:
            print(f"[Coreference] Heuristic: '{query}' -> '{resolved}'")
        return resolved, {}
    except Exception as e:
        print(f"[Coreference] Error: {e}")
        # Fall back to heuristic
        resolved = resolve_coreferences_heuristic(query, history)
        return resolved, {}
    
    return query, {}


async def extract_conversation_context(
    history: List[Dict[str, Any]]
) -> ConversationContext:
    """
    Extract comprehensive context from conversation history.
    
    Args:
        history: Conversation history
        
    Returns:
        ConversationContext with themes, entities, etc.
    """
    if not history:
        return ConversationContext(
            themes=[],
            current_topic="",
            resolved_entities={},
            key_entities_mentioned=[],
            last_user_question="",
            last_assistant_response="",
            conversation_summary="",
            pronoun_mappings={}
        )
    
    # Extract last user and assistant messages
    last_user = ""
    last_assistant = ""
    
    for msg in reversed(history):
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user" and not last_user:
            last_user = content
        elif role == "assistant" and not last_assistant:
            last_assistant = content
        if last_user and last_assistant:
            break
    
    # Heuristic theme extraction (fast)
    themes = extract_themes_heuristic(history)
    
    # Current topic is the most recent theme or last user question
    current_topic = themes[0] if themes else last_user[:50]
    
    return ConversationContext(
        themes=themes,
        current_topic=current_topic,
        resolved_entities={},  # Populated on-demand
        key_entities_mentioned=themes,
        last_user_question=last_user,
        last_assistant_response=last_assistant,
        conversation_summary="",  # Can be populated via LLM if needed
        pronoun_mappings={}
    )


def boost_by_conversation_context(
    chunks: List[Dict[str, Any]],
    context: ConversationContext,
    boost_factor: float = 0.1
) -> List[Dict[str, Any]]:
    """
    Rerank chunks based on conversation context.
    
    Args:
        chunks: Retrieved chunks
        context: Conversation context
        boost_factor: How much to boost matching chunks
        
    Returns:
        Reranked chunks
    """
    if not context.themes or not chunks:
        return chunks
    
    # Score each chunk by theme overlap
    scored_chunks = []
    
    for chunk in chunks:
        text = chunk.get("text", "").lower()
        base_score = chunk.get("score", 0.5)
        
        # Boost for theme matches
        theme_matches = sum(1 for theme in context.themes if theme.lower() in text)
        theme_boost = min(boost_factor * theme_matches, 0.3)  # Max 0.3 boost
        
        # Boost for current topic match
        topic_boost = boost_factor / 2 if context.current_topic and context.current_topic.lower() in text else 0
        
        # Boost for recent mention in conversation
        recent_boost = 0
        if context.key_entities_mentioned:
            entity_matches = sum(1 for e in context.key_entities_mentioned if e.lower() in text)
            recent_boost = min(boost_factor / 2 * entity_matches, 0.15)
        
        new_score = min(base_score + theme_boost + topic_boost + recent_boost, 1.0)
        
        scored_chunks.append((new_score, chunk))
    
    # Sort by new score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # Return reranked chunks with updated scores
    result = []
    for new_score, chunk in scored_chunks:
        chunk["score"] = new_score
        chunk["context_boosted"] = True
        result.append(chunk)
    
    return result


async def get_contextualized_query(
    query: str,
    history: List[Dict[str, Any]]
) -> tuple[str, ConversationContext, Dict[str, str]]:
    """
    Get query with conversation context applied.
    
    Returns:
        Tuple of (resolved_query, conversation_context, pronoun_mappings)
    """
    # Extract conversation context
    conv_context = await extract_conversation_context(history)
    
    # Resolve coreferences
    resolved_query, mappings = await resolve_coreferences(query, history)
    conv_context.pronoun_mappings = mappings
    
    return resolved_query, conv_context, mappings
