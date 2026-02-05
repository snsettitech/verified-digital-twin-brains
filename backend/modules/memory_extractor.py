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

Return a JSON array of memory objects. If no memories can be extracted, return an empty array [].
Example format:
[
  {
    "type": "goal",
    "value": "User wants to build a VC brain to track investment decisions",
    "evidence": "I'm trying to create a VC brain that helps me remember my investment thesis",
    "confidence": 0.9
  }
]

ONLY return valid JSON, no markdown formatting or explanation."""


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
    
    # Format transcript for prompt
    transcript_text = "\n".join([
        f"{turn.get('role', 'unknown').upper()}: {turn.get('content', '')}"
        for turn in transcript
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
                    "content": "You are a precise memory extraction system. Output only valid JSON arrays."
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
            # Handle both array and object responses
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                # If wrapped in an object, extract the array
                memories_data = parsed.get("memories", parsed.get("items", []))
            else:
                memories_data = parsed
                
            if not isinstance(memories_data, list):
                memories_data = []
                
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
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        
        return ExtractionResult(
            memories=memories,
            total_extracted=len(memories),
            transcript_turns=len(transcript),
            extraction_time_ms=elapsed_ms
        )
        
    except Exception as e:
        logger.error(f"Memory extraction failed: {e}")
        elapsed_ms = int((time.time() - start_time) * 1000)
        return ExtractionResult(
            memories=[],
            total_extracted=0,
            transcript_turns=len(transcript),
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
