# backend/modules/memory_extractor.py
"""Memory extraction pipeline for Interview Mode.

Extracts structured memories from interview transcripts using LLM.
Memory types: intent, goal, constraint, preference, boundary
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import json
import os
import logging
import re

logger = logging.getLogger(__name__)


class ExtractedMemory(BaseModel):
    """A single memory extracted from transcript."""
    type: str = Field(..., description="Memory type: intent, goal, constraint, preference, boundary")
    value: str = Field(..., description="The actual memory content")
    evidence: str = Field(..., description="Quote or paraphrase from transcript")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    session_id: str = Field(default="")
    source: str = Field(default="interview_mode")


class ExtractionResult(BaseModel):
    """Result from memory extraction."""
    memories: List[ExtractedMemory]
    total_extracted: int
    transcript_turns: int
    extraction_time_ms: int


EXTRACTION_PROMPT = """You are a memory extraction system. Analyze the following interview transcript and extract structured memories about the user.

For each distinct piece of information the user reveals, create a memory item with one of these types:
- **intent**: What the user is trying to accomplish right now
- **goal**: Short or long-term objectives the user has
- **constraint**: Limitations, restrictions, or requirements the user faces
- **preference**: How the user likes things done, their style or approach
- **boundary**: Things the user won't do, topics they avoid, hard limits

For each memory, provide:
1. `type`: One of the five types above
2. `value`: A clear, concise statement of the memory (as if you're storing it for future reference)
3. `evidence`: A direct quote or close paraphrase from the transcript that supports this
4. `confidence`: A score from 0.0 to 1.0 based on how explicitly/clearly the user stated this

Guidelines:
- Extract ONLY information the user explicitly stated or strongly implied
- Don't infer beyond what's directly supported by the transcript
- Prefer multiple specific memories over one vague one
- Be conservative with confidence scores:
  - 0.9-1.0: Directly and explicitly stated
  - 0.7-0.8: Clearly implied with context
  - 0.5-0.6: Reasonable inference
  - Below 0.5: Don't include

TRANSCRIPT:
{transcript}

Return a JSON object with this exact shape:
{
  "memories": [
    {
      "type": "goal",
      "value": "User wants to build a VC brain to track investment decisions",
      "evidence": "I'm trying to create a VC brain that helps me remember my investment thesis",
      "confidence": 0.9
    }
  ]
}

If no memories can be extracted, return {"memories": []}.
ONLY return valid JSON, no markdown formatting or explanation."""

FILLER_ONLY_RE = re.compile(r"^(uh+|um+|hmm+|mm+|ah+|oh+|okay+|ok+|bye+|hi+|hello+)[\.\!\?]*$", re.IGNORECASE)
ASSISTANT_ACK_ONLY_RE = re.compile(
    r"^(got it|understood|sure|okay|ok|great|thanks|thank you|absolutely|of course|alright|noted|right)[\.\!\s]*$",
    re.IGNORECASE,
)
BOUNDARY_RE = re.compile(r"\b(do not|don't|never|avoid|must not|cannot|can't|should not|no fluff)\b", re.IGNORECASE)
PREFERENCE_RE = re.compile(r"\b(i prefer|i like|i value|my style|my communication style|direct|structured|practical)\b", re.IGNORECASE)
GOAL_RE = re.compile(r"\b(i want|i am building|i'm building|purpose is|primary use case|help others|understand me)\b", re.IGNORECASE)
CONSTRAINT_RE = re.compile(r"\b(if you don't know|if you do not know|ask for missing information|escalate to)\b", re.IGNORECASE)
IDENTITY_RE = re.compile(r"\bmy name is\b", re.IGNORECASE)


def _coalesce_transcript(transcript: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Merge fragmented turns from realtime streams and drop low-signal fillers."""
    merged: List[Dict[str, str]] = []
    for turn in transcript:
        role = (turn.get("role") or "").strip().lower()
        content = (turn.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if len(content) <= 20 and FILLER_ONLY_RE.match(content):
            continue
        if (
            role == "assistant"
            and len(content) <= 80
            and "?" not in content
            and ASSISTANT_ACK_ONLY_RE.match(content)
            and merged
            and merged[-1]["role"] == "user"
        ):
            # Realtime voice sessions often interleave tiny assistant acknowledgements
            # ("Got it.", "Understood.") between fragmented user phrases.
            # Dropping those keeps the user thought intact for extraction.
            continue
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] = f"{merged[-1]['content']} {content}".strip()
        else:
            merged.append({"role": role, "content": content})
    return merged


def _coerce_memories_data(parsed: Any) -> List[Dict[str, Any]]:
    """Accept multiple JSON shapes and normalize to a list of memory dicts."""
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    if isinstance(parsed, dict):
        for key in ("memories", "items", "data", "results"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if {"type", "value"}.issubset(set(parsed.keys())):
            return [parsed]
        if parsed and all(isinstance(v, dict) for v in parsed.values()):
            return [item for item in parsed.values() if isinstance(item, dict)]

    return []


def _heuristic_extract_memories(transcript: List[Dict[str, str]], session_id: str) -> List[ExtractedMemory]:
    """
    Deterministic fallback extractor.
    Used when model output is empty/malformed so owner training does not become a no-op.
    """
    memories: List[ExtractedMemory] = []
    seen: set[tuple[str, str]] = set()

    user_turns = [t.get("content", "").strip() for t in transcript if t.get("role") == "user"]
    for content in user_turns:
        if not content or len(content) < 12:
            continue

        mem_type = None
        confidence = 0.66
        if BOUNDARY_RE.search(content):
            mem_type = "boundary"
            confidence = 0.8
        elif CONSTRAINT_RE.search(content):
            mem_type = "constraint"
            confidence = 0.75
        elif IDENTITY_RE.search(content):
            mem_type = "intent"
            confidence = 0.82
        elif PREFERENCE_RE.search(content):
            mem_type = "preference"
            confidence = 0.72
        elif GOAL_RE.search(content):
            mem_type = "goal"
            confidence = 0.7

        if not mem_type:
            continue

        normalized_value = content.strip()
        dedupe_key = (mem_type, normalized_value.lower())
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        memories.append(
            ExtractedMemory(
                type=mem_type,
                value=normalized_value,
                evidence=content.strip(),
                confidence=confidence,
                timestamp=datetime.utcnow().isoformat(),
                session_id=session_id,
                source="interview_mode",
            )
        )

    return memories


async def extract_memories(
    transcript: List[Dict[str, str]],
    session_id: str
) -> ExtractionResult:
    """
    Extract structured memories from interview transcript using LLM.
    
    Args:
        transcript: List of turns with 'role' and 'content' keys
        session_id: The interview session ID
        
    Returns:
        ExtractionResult with list of ExtractedMemory objects
    """
    import time
    start_time = time.time()
    
    if not transcript:
        return ExtractionResult(
            memories=[],
            total_extracted=0,
            transcript_turns=0,
            extraction_time_ms=0
        )
    
    normalized_transcript = _coalesce_transcript(transcript)

    # Format transcript for prompt
    transcript_text = "\n".join([
        f"{turn.get('role', 'unknown').upper()}: {turn.get('content', '')}"
        for turn in normalized_transcript
    ])
    
    # Call LLM for extraction
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise memory extraction system. "
                        "Output only valid JSON objects with a top-level `memories` array."
                    ),
                },
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(transcript=transcript_text)
                }
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        
        # Parse JSON response
        try:
            # Handle multiple model response shapes.
            parsed = json.loads(content)
            memories_data = _coerce_memories_data(parsed)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response: {e}")
            memories_data = []
        
        # Convert to ExtractedMemory objects
        memories = []
        for item in memories_data:
            if not isinstance(item, dict):
                continue
                
            memory_type = item.get("type", "").lower()
            if memory_type not in ["intent", "goal", "constraint", "preference", "boundary"]:
                continue
                
            try:
                memory = ExtractedMemory(
                    type=memory_type,
                    value=item.get("value", ""),
                    evidence=item.get("evidence", ""),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
                    timestamp=datetime.utcnow().isoformat(),
                    session_id=session_id,
                    source="interview_mode"
                )
                memories.append(memory)
            except Exception as e:
                logger.warning(f"Failed to create memory from item: {e}")
                continue
        
        if not memories:
            memories = _heuristic_extract_memories(normalized_transcript, session_id)

        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ExtractionResult(
            memories=memories,
            total_extracted=len(memories),
            transcript_turns=len(normalized_transcript),
            extraction_time_ms=elapsed_ms
        )
        
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        elapsed_ms = int((time.time() - start_time) * 1000)
        fallback_memories = _heuristic_extract_memories(normalized_transcript, session_id)
        return ExtractionResult(
            memories=fallback_memories,
            total_extracted=len(fallback_memories),
            transcript_turns=len(normalized_transcript),
            extraction_time_ms=elapsed_ms
        )


async def detect_conflicts(
    new_memories: List[ExtractedMemory],
    existing_memories: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Detect conflicts between new and existing memories.
    
    Returns list of conflict objects with:
    - new_memory: The new memory that conflicts
    - existing_memory: The existing memory it conflicts with
    - conflict_type: Type of conflict (contradiction, update, etc.)
    - resolution: Suggested resolution
    """
    conflicts = []
    
    for new_mem in new_memories:
        for existing in existing_memories:
            # Simple keyword-based conflict detection
            if new_mem.type == existing.get("type"):
                # Same type - check for value similarity/contradiction
                new_value = new_mem.value.lower()
                existing_value = existing.get("value", "").lower()
                
                # Check for explicit contradictions
                contradiction_pairs = [
                    ("want", "don't want"),
                    ("like", "dislike"),
                    ("prefer", "avoid"),
                    ("yes", "no"),
                ]
                
                for pos, neg in contradiction_pairs:
                    if (pos in new_value and neg in existing_value) or \
                       (neg in new_value and pos in existing_value):
                        conflicts.append({
                            "new_memory": new_mem.model_dump(),
                            "existing_memory": existing,
                            "conflict_type": "contradiction",
                            "resolution": "mark_superseded"
                        })
                        break
    
    return conflicts


def score_memory_importance(memory: ExtractedMemory) -> float:
    """
    Score a memory's importance for prioritization.
    
    Factors:
    - Type priority (boundaries > constraints > goals > preferences > intents)
    - Confidence level
    - Value specificity
    """
    from modules.zep_memory import MEMORY_PRIORITY
    
    type_weight = 1.0 / MEMORY_PRIORITY.get(memory.type, 5)
    confidence_weight = memory.confidence
    
    # Specificity heuristic: longer, more detailed values are more specific
    specificity = min(1.0, len(memory.value) / 200)
    
    return (type_weight * 0.4) + (confidence_weight * 0.4) + (specificity * 0.2)
