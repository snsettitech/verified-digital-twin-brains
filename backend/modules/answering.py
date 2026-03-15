"""
Answering Module: Legacy answer generation compatibility surface.

The authoritative chat runtime is `modules.agent` + `modules.inference_router`.
This module is retained for older tests and compatibility-only call sites.

Supports legacy provider switching for simple context -> answer generation:
- OpenAI: `OPENAI_MODEL` (default `gpt-4o`)
- Gemini: `GEMINI_MODEL` via Google's OpenAI-compatible endpoint
- Cerebras: Llama 3.3 70B

Environment Variables:
    INFERENCE_PROVIDER: "openai" (default), "gemini", or "cerebras"
    OPENAI_MODEL: OpenAI chat model for compatibility calls
    GEMINI_MODEL: Gemini text model for compatibility calls
    CEREBRAS_API_KEY: Required if using Cerebras

Usage:
    from modules.answering import generate_answer
    
    # Uses provider from environment
    result = generate_answer(query, contexts)
    print(result["answer"])
"""
from modules.clients import get_gemini_client, get_openai_client
import os
import logging
import re
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = (
    """You are {twin_name}.

You speak in the first person as {twin_name}. You are not a generic assistant.
You should sound like the actual person: their judgment, tone, vocabulary,
cadence, and way of thinking should come through naturally from the source
material and the active persona.

Stay in character at all times.
- Never say "as an AI", "as a language model", or anything similar.
- Do not describe yourself as a system unless the user directly asks.
- If the user asks whether you are real, say once, briefly, that you are a
  digital version of {twin_name}, then move on.
- Speak directly. No filler. No corporate language. No generic assistant
  phrases like "Great question" or "Certainly."

Before answering, think privately about:
1. What is this person really asking?
2. What in the knowledge base is actually relevant?
3. What do I honestly think?
4. What would I tell them to do next?
5. What one question would help me give a better answer?

Do not output these steps.
Do not use section headers.
Do not expose your reasoning process.
Write the answer as natural conversational prose.

HOW TO RESPOND
- Start with the substance immediately.
- Keep simple answers short.
- Go deeper only when the question deserves it.
- Give a real point of view, not a safe summary.
- If the user asks what you can or cannot do, answer that in one sentence and
  pivot quickly to what you can help with.
- If multiple sources disagree, say so plainly and give your best judgment.
- If the question is ambiguous and clarification is genuinely needed, ask for
  clarification instead of guessing.
- Sound like a person talking, not a report being generated.

WHEN EVID"""
    """ENCE IS THIN
- Never refuse.
- Never output labels like "INSUFFICIENT EVID"""
    """ENCE".
- Never mention chunk counts, retrieval scores, thresholds, or internal mechanics.
- Give your honest short take based on what you do know.
- Be transparent that you are working from limited information in your
  knowledge base.
- Pivot forward like a person would: say what you can say, then ask one direct
  question that would help you give a better answer.
- Use this pattern: "I don't have a lot in my knowledge base on that
  specifically, but here's how I'd think about it based on what I do know:
  [brief take]. [one direct question]."

CITATIONS
- When a specific source materially supports a claim, cite it inline as [1]
  or [2].
- Keep citations minimal and unobtrusive.
- Never output raw source IDs, chunk IDs, or internal metadata labels like
  [Sou"""
    """rce: abc123] or [chunk id: xyz].
- verified_qa sources are the strongest evidence and should be weighted most
  heavily when relevant.

CONVERSATION RULE
- End every response with exactly one direct question.
- The question must be specific to the user's situation.
- Do not end with multiple questions.
- Do not end with a list of options.
- The question should move the conversation forward.

WHAT YOU CANNOT DO
- You cannot take actions on {twin_name}'s behalf.
- You cannot commit money, make introductions, review documents directly,
  attend meetings, or make promises.
- When asked to do something you cannot do, say so briefly and pivot to what
  you actually can help with: thinking through the problem, improving the
  approach, sharpening the material, or clarifying what matters most.

YOUR KNOWLEDGE BASE
{retrieved_context_block}

Use the knowledge base to ground your answer, but do not quote it robotically.
Digest it and speak from it naturally.

Conversation so far:
{conversation_history}

Twin: {twin_name}
Namespace: {creator_namespace}
Persona: {active_persona}
"""
)

# Provider configuration
INFERENCE_PROVIDER = os.getenv("INFERENCE_PROVIDER", "openai").lower()
INFERENCE_FALLBACK_ENABLED = os.getenv("INFERENCE_FALLBACK_ENABLED", "true").lower() == "true"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

if INFERENCE_PROVIDER not in ["openai", "gemini", "cerebras"]:
    logger.warning(f"[Answering] Unknown provider '{INFERENCE_PROVIDER}', using 'openai'")
    INFERENCE_PROVIDER = "openai"

logger.info(f"[Answering] Using inference provider: {INFERENCE_PROVIDER}")


def build_retrieved_context_block(contexts: List[Dict[str, Any]]) -> str:
    """Render retrieved context with numeric labels for prompt injection."""
    context_parts: List[str] = []
    for i, chunk in enumerate(contexts, start=1):
        text = re.sub(r"\s+", " ", str(chunk.get("text") or "").strip())
        if not text:
            continue
        strategy = str(chunk.get("strategy_name") or "unknown").strip() or "unknown"
        try:
            score = float(chunk.get("score", chunk.get("vector_score", 0.0)) or 0.0)
        except Exception:
            score = 0.0
        context_parts.append(
            f"[{i}] {text}\n"
            f"   strategy: {strategy} | score: {score:.2f}"
        )
    return "\n\n".join(context_parts) if context_parts else "- None available."


def _render_system_prompt(contexts: List[Dict[str, Any]]) -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(
        twin_name="Digital Twin",
        retrieved_context_block=build_retrieved_context_block(contexts),
        conversation_history="- None available.",
        creator_namespace="unknown",
        active_persona="default",
    )


def _build_prompt(query: str, contexts: List[Dict]) -> str:
    """Build the compatibility user prompt from query and contexts."""
    context_text = build_retrieved_context_block(contexts)
    return (
        "Use only the retrieved knowledge above. Stay conversational, keep citations inline as "
        "[1] or [2] when they materially help, and end with one direct question.\n\n"
        f"Retrieved knowledge:\n{context_text}\n\n"
        f"User query: {query}\n\n"
        "Answer:"
    )


def _calculate_confidence(contexts: List[Dict]) -> float:
    """Calculate average confidence score from contexts."""
    return sum([c.get('score', 0) for c in contexts]) / len(contexts) if contexts else 0


def _generate_answer_openai(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """Generate answer using OpenAI."""
    client = get_openai_client()
    prompt = _build_prompt(query, contexts)
    
    # Intentional legacy bypass: this compatibility surface is kept for older tests/callers.
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    
    answer = response.choices[0].message.content
    avg_score = _calculate_confidence(contexts)
    
    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts],
        "provider": "openai",
        "model": OPENAI_MODEL
    }


def _generate_answer_gemini(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """Generate answer using Gemini via the OpenAI-compatible endpoint."""
    client = get_gemini_client()
    prompt = _build_prompt(query, contexts)

    # Intentional legacy bypass: this compatibility surface is kept for older tests/callers.
    response = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    answer = response.choices[0].message.content
    avg_score = _calculate_confidence(contexts)

    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts],
        "provider": "gemini",
        "model": GEMINI_MODEL
    }


def _generate_answer_cerebras(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """Generate answer using Cerebras."""
    from modules.inference_cerebras import CerebrasClient
    
    client = CerebrasClient()
    prompt = _build_prompt(query, contexts)
    
    response = client.generate(
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2048
    )
    
    answer = response.choices[0].message.content
    avg_score = _calculate_confidence(contexts)
    
    return {
        "answer": answer,
        "confidence_score": avg_score,
        "citations": [c['source_id'] for c in contexts],
        "provider": "cerebras",
        "model": client.model
    }


def generate_answer(query: str, contexts: List[Dict]) -> Dict[str, Any]:
    """
    Generate answer using configured provider.
    
    Provider is determined by INFERENCE_PROVIDER environment variable:
    - "openai" (default): Uses OPENAI_MODEL
    - "gemini": Uses GEMINI_MODEL via Google OpenAI compatibility
    - "cerebras": Uses Llama 3.3 70B on Cerebras
    
    With INFERENCE_FALLBACK_ENABLED=true, automatically falls back to OpenAI
    if Gemini or Cerebras fails.
    
    Args:
        query: User query string
        contexts: List of context dicts with 'text', 'score', 'source_id'
        
    Returns:
        Dict with 'answer', 'confidence_score', 'citations', 'provider', 'model'
    """
    # Try primary provider
    if INFERENCE_PROVIDER == "cerebras":
        try:
            return _generate_answer_cerebras(query, contexts)
        except Exception as e:
            logger.warning(f"[Answering] Cerebras failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI")
                return _generate_answer_openai(query, contexts)
            raise

    if INFERENCE_PROVIDER == "gemini":
        try:
            return _generate_answer_gemini(query, contexts)
        except Exception as e:
            logger.warning(f"[Answering] Gemini failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI")
                return _generate_answer_openai(query, contexts)
            raise
    
    # Default: OpenAI
    return _generate_answer_openai(query, contexts)


async def _generate_answer_stream_openai(query: str, contexts: List[Dict]):
    """Generate streaming answer using OpenAI."""
    client = get_openai_client()
    prompt = _build_prompt(query, contexts)
    
    # Intentional legacy bypass: this compatibility surface is kept for older tests/callers.
    stream = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        stream=True
    )
    
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def _generate_answer_stream_gemini(query: str, contexts: List[Dict]):
    """Generate streaming answer using Gemini via the OpenAI-compatible endpoint."""
    client = get_gemini_client()
    prompt = _build_prompt(query, contexts)

    # Intentional legacy bypass: this compatibility surface is kept for older tests/callers.
    stream = client.chat.completions.create(
        model=GEMINI_MODEL,
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content


async def _generate_answer_stream_cerebras(query: str, contexts: List[Dict]):
    """Generate streaming answer using Cerebras."""
    from modules.inference_cerebras import CerebrasClient
    
    client = CerebrasClient()
    prompt = _build_prompt(query, contexts)
    
    async for chunk in client.generate_stream_async(
        messages=[
            {"role": "system", "content": _render_system_prompt(contexts)},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2048
    ):
        yield chunk


async def generate_answer_stream(query: str, contexts: List[Dict]):
    """
    Generate streaming answer using configured provider.
    
    Args:
        query: User query string
        contexts: List of context dicts
        
    Yields:
        Text chunks of the generated answer
    """
    # Try primary provider
    if INFERENCE_PROVIDER == "cerebras":
        try:
            async for chunk in _generate_answer_stream_cerebras(query, contexts):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[Answering] Cerebras streaming failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI streaming")
                async for chunk in _generate_answer_stream_openai(query, contexts):
                    yield chunk
                return
            raise

    if INFERENCE_PROVIDER == "gemini":
        try:
            async for chunk in _generate_answer_stream_gemini(query, contexts):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"[Answering] Gemini streaming failed: {e}")
            if INFERENCE_FALLBACK_ENABLED:
                logger.info("[Answering] Falling back to OpenAI streaming")
                async for chunk in _generate_answer_stream_openai(query, contexts):
                    yield chunk
                return
            raise
    
    # Default: OpenAI
    async for chunk in _generate_answer_stream_openai(query, contexts):
        yield chunk


def get_answering_health() -> Dict[str, Any]:
    """
    Get health status of answering module.
    
    Returns:
        Dict with provider status
    """
    return {
        "provider": INFERENCE_PROVIDER,
        "fallback_enabled": INFERENCE_FALLBACK_ENABLED,
        "status": "healthy"
    }
