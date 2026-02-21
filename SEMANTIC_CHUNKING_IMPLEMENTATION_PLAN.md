# Semantic Chunking Implementation Plan

## Quick Start: Priority 1 Implementation

This document provides a step-by-step implementation guide for the highest-impact, lowest-complexity improvements.

---

## Phase 1: Structure-Aware Chunking (Days 1-3)

### Step 1.1: Enhanced Chunk Schema

**File:** `backend/modules/schemas.py`

Add new chunk schema:

```python
class SemanticChunkMetadata(BaseModel):
    """Rich metadata for semantic chunks."""
    
    # Core content
    chunk_text: str
    chunk_summary: Optional[str] = None
    chunk_title: Optional[str] = None
    
    # Document context
    doc_title: str
    doc_id: str
    source_type: str  # pdf, youtube, transcript, etc.
    created_at: Optional[datetime] = None
    
    # Structural metadata
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    section_level: int = 0
    
    # Semantic metadata
    chunk_type: str = "paragraph"  # heading, paragraph, list, table
    speaker: Optional[str] = None  # For transcripts
    topics: List[str] = Field(default_factory=list)
    
    # Positioning
    chunk_index: int = 0
    total_chunks: int = 1
    
    # What gets embedded
    embedding_text: Optional[str] = None
```

### Step 1.2: Semantic Boundary Detection

**File:** `backend/modules/doc_sectioning.py`

Add semantic chunking function:

```python
async def detect_semantic_boundaries(
    sentences: List[str],
    similarity_threshold: float = 0.7,
) -> List[int]:
    """
    Detect semantic boundaries between sentences using embeddings.
    
    Returns list of indices where new chunks should start.
    """
    from sentence_transformers import SentenceTransformer
    
    if len(sentences) <= 1:
        return [0]
    
    # Load model (cache it)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Embed all sentences
    embeddings = model.encode(sentences)
    
    # Calculate similarities between consecutive sentences
    boundaries = [0]  # Always start at first sentence
    
    for i in range(len(embeddings) - 1):
        similarity = cosine_similarity(
            embeddings[i].reshape(1, -1),
            embeddings[i + 1].reshape(1, -1)
        )[0][0]
        
        # If similarity drops below threshold, start new chunk
        if similarity < similarity_threshold:
            boundaries.append(i + 1)
    
    return boundaries
```

### Step 1.3: Speaker Turn Detection

```python
def detect_speaker_turns(text: str) -> List[Dict[str, Any]]:
    """
    Detect speaker turns in transcripts.
    
    Patterns:
    - "John: Hello everyone"
    - "[Sarah] How are you?"
    - "Speaker 1: Welcome"
    """
    speaker_patterns = [
        r'^([A-Z][a-zA-Z\s]+):\s*',           # Name: text
        r'^\[([A-Z][a-zA-Z\s]+)\]\s*',         # [Name] text
        r'^(Speaker\s+\d+):\s*',              # Speaker 1: text
    ]
    
    segments = []
    current_speaker = None
    current_text = []
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        speaker_found = None
        for pattern in speaker_patterns:
            match = re.match(pattern, line)
            if match:
                speaker_found = match.group(1).strip()
                text_content = line[match.end():].strip()
                break
        
        if speaker_found:
            # Save previous segment
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'text': '\n'.join(current_text)
                })
            # Start new segment
            current_speaker = speaker_found
            current_text = [text_content] if 'text_content' in locals() else [line]
        else:
            current_text.append(line)
    
    # Don't forget last segment
    if current_speaker and current_text:
        segments.append({
            'speaker': current_speaker,
            'text': '\n'.join(current_text)
        })
    
    return segments
```

---

## Phase 2: Rich Metadata Generation (Days 4-6)

### Step 2.1: Chunk Summarization

**File:** `backend/modules/chunk_summarizer.py` (NEW)

```python
"""Generate summaries for chunks using LLM."""

import os
from typing import List, Optional
from modules.clients import get_openai_client

CHUNK_SUMMARIZER_MODEL = os.getenv("CHUNK_SUMMARIZER_MODEL", "gpt-4o-mini")
CHUNK_SUMMARY_MAX_TOKENS = 100


async def generate_chunk_summary(
    chunk_text: str,
    doc_title: Optional[str] = None,
    section_title: Optional[str] = None,
) -> str:
    """
    Generate a 1-2 sentence summary of a chunk.
    
    This summary will be used for embedding instead of full text.
    """
    if not chunk_text or len(chunk_text) < 100:
        return chunk_text
    
    client = get_openai_client()
    
    context = ""
    if doc_title:
        context += f"Document: {doc_title}\n"
    if section_title:
        context += f"Section: {section_title}\n"
    
    prompt = f"""{context}
Content:
{chunk_text[:2000]}

Provide a 1-2 sentence summary that captures the key information.
Focus on facts, figures, and main points. Be concise."""
    
    try:
        response = client.chat.completions.create(
            model=CHUNK_SUMMARIZER_MODEL,
            messages=[
                {"role": "system", "content": "You create concise summaries for document chunks."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=CHUNK_SUMMARY_MAX_TOKENS,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Chunk summarization failed: {e}")
        # Fallback: first sentence + ellipsis
        first_sentence = chunk_text.split('.')[0]
        return f"{first_sentence}."[:200]


async def generate_chunk_title(
    chunk_text: str,
    section_title: Optional[str] = None,
) -> str:
    """Generate a descriptive title for a chunk."""
    if section_title:
        return section_title
    
    # Extract first line if it looks like a heading
    first_line = chunk_text.split('\n')[0].strip()
    if len(first_line) < 100 and not first_line.endswith('.'):
        return first_line
    
    # Generate with LLM
    client = get_openai_client()
    
    prompt = f"""Generate a short, descriptive title (3-7 words) for this content:

{chunk_text[:1000]}

Title:"""
    
    try:
        response = client.chat.completions.create(
            model=CHUNK_SUMMARIZER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip().strip('"')
    except Exception:
        return "Section"  # Fallback
```

### Step 2.2: Contextual Embedding Text Builder

```python
def build_embedding_text(
    chunk_summary: str,
    chunk_title: Optional[str] = None,
    doc_title: Optional[str] = None,
    section_path: Optional[str] = None,
    source_type: Optional[str] = None,
) -> str:
    """
    Build the text that will actually be embedded.
    
    Includes contextual headers for better retrieval.
    """
    parts = []
    
    # Document context
    if doc_title:
        parts.append(f"Document: {doc_title}")
    
    if section_path:
        parts.append(f"Section: {section_path}")
    
    if chunk_title:
        parts.append(f"Topic: {chunk_title}")
    
    if source_type:
        parts.append(f"Type: {source_type}")
    
    # Separator
    if parts:
        parts.append("")
    
    # Main content
    parts.append(chunk_summary)
    
    return "\n".join(parts)
```

---

## Phase 3: Integration (Days 7-8)

### Step 3.1: New Chunking Pipeline

**File:** `backend/modules/semantic_chunker.py` (NEW)

```python
"""
Semantic chunking pipeline combining structure detection, 
semantic boundaries, and rich metadata.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from modules.doc_sectioning import extract_section_blocks, _detect_heading
from modules.chunk_summarizer import generate_chunk_summary, generate_chunk_title


@dataclass
class SemanticChunk:
    chunk_text: str
    chunk_summary: str
    chunk_title: str
    doc_title: str
    doc_id: str
    source_type: str
    section_title: Optional[str] = None
    section_path: Optional[str] = None
    section_level: int = 0
    chunk_type: str = "paragraph"
    speaker: Optional[str] = None
    chunk_index: int = 0
    total_chunks: int = 1
    embedding_text: str = ""


async def create_semantic_chunks(
    text: str,
    doc_title: str,
    doc_id: str,
    source_type: str = "document",
    chunk_size: int = 500,
    overlap: int = 50,
) -> List[SemanticChunk]:
    """
    Create semantic chunks with rich metadata.
    
    Process:
    1. Detect structure (headings, speaker turns)
    2. Apply semantic chunking
    3. Generate summaries
    4. Build embedding text with context
    """
    # Step 1: Extract structure blocks
    blocks = extract_section_blocks(text)
    
    chunks = []
    chunk_index = 0
    
    for block in blocks:
        block_text = str(block.get("text") or "").strip()
        if not block_text:
            continue
        
        section_title = block.get("section_title")
        section_path = block.get("section_path")
        
        # Step 2: Smart chunking based on content type
        if source_type == "transcript" and block_text.count('\n') > 3:
            # Use speaker turn detection for transcripts
            speaker_segments = detect_speaker_turns(block_text)
            for segment in speaker_segments:
                chunk = await _create_chunk_from_segment(
                    segment=segment,
                    doc_title=doc_title,
                    doc_id=doc_id,
                    source_type=source_type,
                    section_title=section_title,
                    section_path=section_path,
                    chunk_index=chunk_index,
                )
                chunks.append(chunk)
                chunk_index += 1
        else:
            # Use semantic chunking
            sub_chunks = _chunk_semantically(
                block_text,
                target_size=chunk_size,
                overlap=overlap,
            )
            
            for sub_chunk_text in sub_chunks:
                chunk = await _create_chunk(
                    text=sub_chunk_text,
                    doc_title=doc_title,
                    doc_id=doc_id,
                    source_type=source_type,
                    section_title=section_title,
                    section_path=section_path,
                    chunk_index=chunk_index,
                )
                chunks.append(chunk)
                chunk_index += 1
    
    # Update total_chunks
    total = len(chunks)
    for chunk in chunks:
        chunk.total_chunks = total
    
    return chunks


async def _create_chunk(
    text: str,
    doc_title: str,
    doc_id: str,
    source_type: str,
    section_title: Optional[str],
    section_path: Optional[str],
    chunk_index: int,
) -> SemanticChunk:
    """Create a single semantic chunk with metadata."""
    
    # Generate summary
    summary = await generate_chunk_summary(
        chunk_text=text,
        doc_title=doc_title,
        section_title=section_title,
    )
    
    # Generate title
    title = await generate_chunk_title(text, section_title)
    
    # Build embedding text
    embedding = build_embedding_text(
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        section_path=section_path,
        source_type=source_type,
    )
    
    return SemanticChunk(
        chunk_text=text,
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        doc_id=doc_id,
        source_type=source_type,
        section_title=section_title,
        section_path=section_path,
        chunk_index=chunk_index,
        embedding_text=embedding,
    )


async def _create_chunk_from_segment(
    segment: Dict[str, str],
    doc_title: str,
    doc_id: str,
    source_type: str,
    section_title: Optional[str],
    section_path: Optional[str],
    chunk_index: int,
) -> SemanticChunk:
    """Create chunk from speaker segment."""
    text = segment['text']
    speaker = segment.get('speaker')
    
    summary = await generate_chunk_summary(text, doc_title, section_title)
    title = f"{speaker}: {summary[:50]}..." if speaker else await generate_chunk_title(text)
    
    embedding = build_embedding_text(
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        section_path=section_path,
        source_type=f"{source_type}_transcript",
    )
    
    return SemanticChunk(
        chunk_text=text,
        chunk_summary=summary,
        chunk_title=title,
        doc_title=doc_title,
        doc_id=doc_id,
        source_type=source_type,
        section_title=section_title,
        section_path=section_path,
        chunk_type="transcript_segment",
        speaker=speaker,
        chunk_index=chunk_index,
        embedding_text=embedding,
    )
```

### Step 3.2: Ingestion Pipeline Integration

Modify `ingestion.py` to use new chunking:

```python
# Add to imports
from modules.semantic_chunker import create_semantic_chunks

# In process_document function, replace:
# OLD:
# chunks = chunk_text_with_metadata(text)

# NEW:
chunks = await create_semantic_chunks(
    text=text,
    doc_title=title,
    doc_id=source_id,
    source_type=source_type,
)

# Store chunks with new metadata
for chunk in chunks:
    vector_metadata = {
        "chunk_text": chunk.chunk_text,
        "chunk_summary": chunk.chunk_summary,
        "chunk_title": chunk.chunk_title,
        "doc_title": chunk.doc_title,
        "source_type": chunk.source_type,
        "section_title": chunk.section_title,
        "section_path": chunk.section_path,
        "chunk_index": chunk.chunk_index,
        "total_chunks": chunk.total_chunks,
        "speaker": chunk.speaker,
    }
    
    # Embed the contextualized text
    embedding = await create_embedding(chunk.embedding_text)
    
    # Store in Pinecone
    await store_chunk(embedding, vector_metadata)
```

---

## Phase 4: Quality Measurement (Day 9)

### Step 4.1: Chunk Quality Evaluator

**File:** `backend/modules/chunk_quality_evaluator.py` (NEW)

```python
"""Evaluate quality of semantic chunks."""

import numpy as np
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer


class ChunkQualityEvaluator:
    """Evaluate semantic chunk quality."""
    
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def evaluate_semantic_coherence(self, chunks: List[str]) -> float:
        """
        Measure how semantically coherent each chunk is.
        
        Returns average intra-chunk similarity.
        Higher = better (sentences in chunk are related).
        """
        scores = []
        
        for chunk in chunks:
            sentences = [s.strip() for s in chunk.split('.') if s.strip()]
            if len(sentences) < 2:
                continue
            
            embeddings = self.model.encode(sentences)
            
            # Calculate pairwise similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    sim = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append(sim)
            
            if similarities:
                scores.append(np.mean(similarities))
        
        return np.mean(scores) if scores else 0.0
    
    def evaluate_topic_purity(self, chunks: List[str]) -> float:
        """
        Measure how focused each chunk is on a single topic.
        
        Uses variance in sentence similarities.
        Lower variance = more focused.
        """
        variances = []
        
        for chunk in chunks:
            sentences = [s.strip() for s in chunk.split('.') if s.strip()]
            if len(sentences) < 3:
                continue
            
            embeddings = self.model.encode(sentences)
            
            # Calculate consecutive similarities
            similarities = []
            for i in range(len(embeddings) - 1):
                sim = np.dot(embeddings[i], embeddings[i + 1]) / (
                    np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1])
                )
                similarities.append(sim)
            
            if similarities:
                variances.append(np.var(similarities))
        
        # Lower variance = higher purity
        avg_variance = np.mean(variances) if variances else 1.0
        return max(0, 1 - avg_variance)
    
    def evaluate_chunking_quality(self, chunks: List[str]) -> Dict[str, float]:
        """Run all quality evaluations."""
        return {
            "semantic_coherence": self.evaluate_semantic_coherence(chunks),
            "topic_purity": self.evaluate_topic_purity(chunks),
            "avg_chunk_size": np.mean([len(c) for c in chunks]),
            "num_chunks": len(chunks),
        }
```

---

## Phase 5: Deployment (Day 10)

### Step 5.1: Feature Flags

Add to `.env`:

```bash
# Semantic Chunking Configuration
SEMANTIC_CHUNKING_ENABLED=false
SEMANTIC_CHUNKING_MODEL=gpt-4o-mini
CHUNK_SUMMARY_MAX_TOKENS=100
CHUNK_TARGET_SIZE=500
CHUNK_SIMILARITY_THRESHOLD=0.7

# Rollout percentage (0-100)
SEMANTIC_CHUNKING_ROLLOUT_PERCENT=0
```

### Step 5.2: A/B Testing

```python
def should_use_semantic_chunking(doc_id: str) -> bool:
    """Determine if document should use new chunking."""
    if not SEMANTIC_CHUNKING_ENABLED:
        return False
    
    # Deterministic assignment based on doc_id
    import hashlib
    doc_hash = int(hashlib.md5(doc_id.encode()).hexdigest(), 16)
    bucket = doc_hash % 100
    
    return bucket < SEMANTIC_CHUNKING_ROLLOUT_PERCENT
```

---

## Success Metrics

After implementation, measure:

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| **Retrieval Precision@5** | ~65% | ~80% | Human evaluation |
| **Semantic Coherence** | ~0.6 | ~0.8 | Embedding similarity |
| **Topic Purity** | ~60% | ~85% | Variance analysis |
| **Chunk Quality Score** | N/A | >0.75 | Combined metric |

---

## Rollback Plan

If issues arise:

1. **Immediate:** Set `SEMANTIC_CHUNKING_ENABLED=false`
2. **Short-term:** Re-ingest affected documents with old chunker
3. **Long-term:** Fix issue and re-test

---

## Next Steps After Phase 1

Once Phase 1 is stable:

1. **Phase 2:** Implement late chunking for long documents
2. **Phase 3:** Add hierarchical chunk linking (prev/next navigation)
3. **Phase 4:** Fine-tune embedding model on your chunks

---

**Estimated Timeline:** 10 days for Phase 1  
**Expected Impact:** 15-20% retrieval improvement  
**Risk Level:** Medium (backward compatible, feature-flagged)
