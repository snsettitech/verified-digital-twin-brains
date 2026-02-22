"""
abstractive_summarizer.py

Phase 3: True Abstractive Summarization
Synthesizes retrieved chunks into coherent narrative summaries using LLM.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from modules.clients import get_async_openai_client
from modules.inference_router import invoke_text


@dataclass
class SummaryResult:
    """Result of abstractive summarization."""
    summary: str
    key_points: List[str]
    citations: List[str]
    synthesis_quality: float  # 0-1 score


# Summarization prompts for different query types
SUMMARIZATION_PROMPTS = {
    "general": """You are a Digital Twin responding to a user's request for a summary.

TASK: Synthesize the provided information into a coherent, natural narrative response.

RETRIEVED INFORMATION:
{chunks_text}

USER QUERY: {query}

INSTRUCTIONS:
1. Create a flowing narrative (2-4 sentences) that feels like a natural conversation
2. Synthesize information across multiple chunks - don't just list facts
3. Maintain the first-person perspective (as if you are the Digital Twin)
4. Include specific details and metrics where available
5. Sound warm, professional, and authentic
6. DO NOT use bullet points or numbered lists
7. DO NOT say "According to the retrieved information" or similar phrases
8. DO NOT mention that you're summarizing documents

OUTPUT FORMAT:
Provide your response as natural paragraph text that directly answers the query.""",

    "background": """You are introducing yourself as a Digital Twin based on your knowledge.

BACKGROUND INFORMATION:
{chunks_text}

INSTRUCTIONS:
1. Write a brief professional introduction (2-3 sentences)
2. Highlight your key expertise and experience
3. Mention specific domains you specialize in
4. Sound confident but approachable
5. Use first-person ("I have...", "My expertise is...")

Write a natural paragraph introducing yourself.""",

    "expertise": """You are explaining your areas of expertise as a Digital Twin.

EXPERTISE INFORMATION:
{chunks_text}

INSTRUCTIONS:
1. Describe your core competencies in 2-3 sentences
2. Mention specific skills, methodologies, or tools you use
3. Explain the value you bring
4. Sound knowledgeable but not boastful
5. Use first-person perspective

Write a natural paragraph about your expertise.""",

    "experience": """You are describing your professional experience as a Digital Twin.

EXPERIENCE INFORMATION:
{chunks_text}

INSTRUCTIONS:
1. Summarize your professional journey in 2-3 sentences
2. Highlight key achievements or notable projects
3. Include metrics or specific outcomes when available
4. Sound experienced and credible
5. Use first-person ("I have worked on...", "I've contributed to...")

Write a natural paragraph about your experience.""",

    "opinion_summary": """You are sharing your perspective based on your knowledge.

BACKGROUND INFORMATION:
{chunks_text}

USER QUERY: {query}

INSTRUCTIONS:
1. Provide your perspective in 2-3 sentences
2. Base your view on the information provided
3. Acknowledge nuances or different angles if relevant
4. Sound thoughtful and considered
5. Use first-person ("I believe...", "In my view...")

Write a natural paragraph expressing your perspective."""
}


def format_chunks_for_summarization(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks for the summarization prompt."""
    formatted = []
    
    for i, chunk in enumerate(chunks[:15], 1):  # Limit to 15 chunks
        text = chunk.get("text", "").strip()
        source = chunk.get("source", "Unknown")
        score = chunk.get("score", 0)
        
        if not text:
            continue
            
        # Truncate long chunks
        if len(text) > 500:
            text = text[:497] + "..."
        
        formatted.append(f"[{i}] Source: {source[:50]}\n{text}\n")
    
    return "\n".join(formatted)


def determine_summary_type(query: str, chunks: List[Dict[str, Any]]) -> str:
    """Determine the best summarization type based on query."""
    query_lower = query.lower()
    
    # Check query keywords
    if any(word in query_lower for word in ["background", "about you", "who are you"]):
        return "background"
    
    if any(word in query_lower for word in ["expertise", "specialize", "skills", "good at"]):
        return "expertise"
    
    if any(word in query_lower for word in ["experience", "worked", "career", "projects"]):
        return "experience"
    
    if any(word in query_lower for word in ["think", "opinion", "view", "believe"]):
        return "opinion_summary"
    
    # Check chunk metadata for hints
    categories = [c.get("category", "").lower() for c in chunks if c.get("category")]
    if "opinion" in categories:
        return "opinion_summary"
    
    return "general"


async def generate_abstractive_summary(
    query: str,
    chunks: List[Dict[str, Any]],
    max_tokens: int = 300,
    temperature: float = 0.4
) -> SummaryResult:
    """
    Generate an abstractive summary from retrieved chunks.
    
    Args:
        query: User query
        chunks: Retrieved chunks with text and metadata
        max_tokens: Maximum tokens for summary
        temperature: Creativity level (0.3-0.5 recommended for factual)
        
    Returns:
        SummaryResult with summary text and metadata
    """
    if not chunks:
        return SummaryResult(
            summary="I don't have enough information to answer that question.",
            key_points=[],
            citations=[],
            synthesis_quality=0.0
        )
    
    # Format chunks for prompt
    chunks_text = format_chunks_for_summarization(chunks)
    
    # Determine summary type
    summary_type = determine_summary_type(query, chunks)
    prompt_template = SUMMARIZATION_PROMPTS.get(summary_type, SUMMARIZATION_PROMPTS["general"])
    
    # Build prompt
    prompt = prompt_template.format(
        chunks_text=chunks_text,
        query=query
    )
    
    # Generate summary using LLM
    try:
        summary_text, route_meta = await invoke_text(
            [{"role": "user", "content": prompt}],
            task="summarization",
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Clean up the summary
        summary_text = summary_text.strip()
        
        # Remove common prefixes the model might add
        prefixes_to_remove = [
            "Summary:",
            "Response:",
            "Answer:",
            "Based on the information provided,",
            "According to the retrieved information,",
        ]
        for prefix in prefixes_to_remove:
            if summary_text.startswith(prefix):
                summary_text = summary_text[len(prefix):].strip()
        
        # Extract citations from chunks
        citations = []
        for chunk in chunks[:5]:
            source_id = chunk.get("source_id")
            if source_id and source_id not in citations:
                citations.append(source_id)
        
        # Generate key points (bullet summary for citations)
        key_points = await extract_key_points(summary_text, chunks)
        
        # Estimate synthesis quality based on coverage
        synthesis_quality = estimate_synthesis_quality(summary_text, chunks)
        
        return SummaryResult(
            summary=summary_text,
            key_points=key_points,
            citations=citations,
            synthesis_quality=synthesis_quality
        )
        
    except Exception as e:
        print(f"[AbstractiveSummarizer] Error: {e}")
        # Fallback to extractive summary
        return create_extractive_fallback(chunks)


async def extract_key_points(summary: str, chunks: List[Dict[str, Any]]) -> List[str]:
    """Extract key points from summary for citation purposes."""
    # Simple extraction: split sentences and pick most substantive
    import re
    sentences = re.split(r'(?<=[.!?])\s+', summary)
    
    # Filter for substantive sentences (not too short, not questions)
    substantive = [
        s.strip() for s in sentences 
        if len(s.strip()) > 30 
        and not s.strip().endswith("?")
        and s.strip()[0].isupper()
    ]
    
    return substantive[:3]


def estimate_synthesis_quality(summary: str, chunks: List[Dict[str, Any]]) -> float:
    """Estimate quality of synthesis (0-1)."""
    import re
    
    if not summary or not chunks:
        return 0.0
    
    # Check coverage: how many chunks contributed unique information
    coverage_score = 0.0
    summary_lower = summary.lower()
    
    for chunk in chunks[:5]:
        text = chunk.get("text", "").lower()
        # Extract key terms from chunk
        terms = set(re.findall(r'\b[a-z]{4,}\b', text))  # Words 4+ chars
        summary_terms = set(re.findall(r'\b[a-z]{4,}\b', summary_lower))
        
        overlap = len(terms.intersection(summary_terms))
        if overlap > 3:  # Significant overlap
            coverage_score += 0.2
    
    # Check narrative flow (sentence count)
    sentence_count = len(re.split(r'(?<=[.!?])\s+', summary))
    flow_score = min(sentence_count / 3, 1.0)  # Ideal: 3+ sentences
    
    # Combine scores
    quality = (coverage_score * 0.6) + (flow_score * 0.4)
    return min(quality, 1.0)


def create_extractive_fallback(chunks: List[Dict[str, Any]]) -> SummaryResult:
    """Create fallback summary using extractive method."""
    # Take first sentence from top 3 chunks
    import re
    
    points = []
    citations = []
    
    for chunk in chunks[:3]:
        text = chunk.get("text", "").strip()
        source_id = chunk.get("source_id")
        
        if text:
            # Get first sentence
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if sentences:
                first = sentences[0].strip()
                if len(first) > 20:
                    points.append(first)
                    if source_id:
                        citations.append(source_id)
    
    summary = " ".join(points) if points else "I don't have specific information about that."
    
    return SummaryResult(
        summary=summary,
        key_points=points,
        citations=citations,
        synthesis_quality=0.3  # Low quality as it's just extraction
    )


async def should_use_abstractive_summary(
    query: str,
    chunks: List[Dict[str, Any]],
    intent_type: Optional[str] = None
) -> bool:
    """
    Determine if abstractive summarization should be used.
    
    Returns True for:
    - Explicit summarization queries
    - "Tell me about yourself" type queries
    - When multiple diverse chunks are retrieved
    """
    query_lower = query.lower()
    
    # Explicit summary keywords
    summary_keywords = [
        "summarize", "summary", "overview", "tell me about",
        "who are you", "what do you do", "your background",
        "describe yourself", "introduce yourself"
    ]
    
    if any(kw in query_lower for kw in summary_keywords):
        return True
    
    # Check intent type
    if intent_type in ["summarization", "entity_lookup"]:
        return True
    
    # Check if we have diverse chunks (good for synthesis)
    if len(chunks) >= 5:
        sources = set(c.get("source_id") for c in chunks)
        if len(sources) >= 2:  # Multiple sources
            return True
    
    return False
