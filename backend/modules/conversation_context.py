"""
conversation_context.py

Phase 2: Conversation Context-Aware Retrieval
Extracts themes and resolves coreferences from conversation history.
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from modules.clients import get_async_openai_client


@dataclass
class ConversationContext:
    """Extracted context from conversation history."""
    themes: List[str]
    current_topic: str
    resolved_entities: Dict[str, str]  # pronoun -> entity
    key_entities_mentioned: List[str]
    last_user_question: str
    last_assistant_response: str
    conversation_summary: str


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
"""


CONVERSATION_SUMMARY_PROMPT = """Summarize the conversation in 2-3 sentences, focusing on:
1. Main topics discussed
2. Key entities mentioned
3. What the user is looking for

Conversation:
{history}

Summary:"""


async def resolve_coreferences(
    query: str,
    history: List[Dict[str, Any]]
) -> str:
    """
    Resolve pronouns and ambiguous references in the query.
    
    Args:
        query: Current user query
        history: Conversation history (last N messages)
        
    Returns:
        Resolved query string
    """
    if not history or not query:
        return query
    
    # Quick check: does query contain pronouns?
    pronouns = ["it", "that", "this", "they", "them", "those", "these"]
    query_lower = query.lower()
    
    has_pronoun = any(f" {p}" in f" {query_lower} " for p in pronouns)
    if not has_pronoun:
        return query
    
    # Format history
    history_text = format_history_for_prompt(history[-5:])  # Last 5 messages
    
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
        
        if resolved and resolved != query:
            print(f"[Coreference] Resolved '{query}' -> '{resolved}'")
            return resolved
            
    except asyncio.TimeoutError:
        print("[Coreference] Timeout, using original query")
    except Exception as e:
        print(f"[Coreference] Error: {e}")
    
    return query


def format_history_for_prompt(history: List[Dict[str, Any]]) -> str:
    """Format conversation history for prompts."""
    lines = []
    for msg in history:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:200]  # Truncate
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def extract_themes_heuristic(history: List[Dict[str, Any]]) -> List[str]:
    """Fast heuristic theme extraction."""
    themes = []
    
    # Extract nouns and proper nouns from recent messages
    for msg in history[-3:]:  # Last 3 messages
        content = msg.get("content", "")
        # Simple extraction: capitalized words and technical terms
        import re
        
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
            conversation_summary=""
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
        resolved_entities={},  # Populated on-demand via resolve_coreferences
        key_entities_mentioned=themes,
        last_user_question=last_user,
        last_assistant_response=last_assistant,
        conversation_summary=""  # Can be populated via LLM if needed
    )


def boost_by_conversation_context(
    chunks: List[Dict[str, Any]],
    context: ConversationContext,
    current_topic: str
) -> List[Dict[str, Any]]:
    """
    Rerank chunks based on conversation context.
    
    Args:
        chunks: Retrieved chunks
        context: Conversation context
        current_topic: Current topic of conversation
        
    Returns:
        Reranked chunks
    """
    if not context.themes or not chunks:
        return chunks
    
    # Score each chunk by theme overlap
    scored_chunks = []
    
    for chunk in chunks:
        text = chunk.get("text", "").lower()
        score = chunk.get("score", 0.5)  # Base score
        
        # Boost for theme matches
        theme_matches = sum(1 for theme in context.themes if theme.lower() in text)
        theme_boost = min(0.1 * theme_matches, 0.3)  # Max 0.3 boost
        
        # Boost for current topic match
        topic_boost = 0.1 if current_topic and current_topic.lower() in text else 0
        
        # Boost for recent mention in conversation
        recent_boost = 0
        if context.key_entities_mentioned:
            entity_matches = sum(1 for e in context.key_entities_mentioned if e.lower() in text)
            recent_boost = min(0.05 * entity_matches, 0.15)
        
        new_score = min(score + theme_boost + topic_boost + recent_boost, 1.0)
        
        scored_chunks.append((new_score, chunk))
    
    # Sort by new score
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # Return reranked chunks
    return [chunk for score, chunk in scored_chunks]


async def get_contextualized_query(
    query: str,
    history: List[Dict[str, Any]]
) -> tuple[str, ConversationContext]:
    """
    Get query with conversation context applied.
    
    Returns:
        Tuple of (resolved_query, conversation_context)
    """
    # Extract conversation context
    conv_context = await extract_conversation_context(history)
    
    # Resolve coreferences
    resolved_query = await resolve_coreferences(query, history)
    
    return resolved_query, conv_context
