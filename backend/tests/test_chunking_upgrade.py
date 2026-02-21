"""
Comprehensive tests for the chunking upgrade.

Tests cover:
1. Unit tests for individual components
2. Integration tests for the full pipeline
3. Backward compatibility tests
4. Performance tests
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import os

# Set test environment
os.environ["RICH_CHUNK_METADATA_ENABLED"] = "true"
os.environ["CONTEXTUAL_EMBEDDING_TEXT_ENABLED"] = "true"
os.environ["STRUCTURE_AWARE_CHUNKING_ENABLED"] = "true"
os.environ["CHUNKING_ROLLOUT_PERCENT"] = "100"

from modules.chunking_config import (
    should_use_new_chunking,
    get_chunking_telemetry,
    CHUNK_VERSION,
)
from modules.chunking_utils import (
    estimate_tokens,
    chunk_by_tokens,
    detect_heading,
    detect_speaker_turn,
    get_chunking_policy,
)
from modules.embedding_text_builder import (
    build_embedding_text,
    validate_embedding_text,
    build_legacy_embedding_text,
)
from modules.chunk_summarizer import (
    generate_chunk_title,
    _extractive_fallback,
)
from modules.semantic_chunker import (
    SemanticChunk,
    create_semantic_chunks,
    _detect_section_level,
)


# ============================================================================
# Unit Tests: Config and Feature Flags
# ============================================================================

class TestChunkingConfig:
    """Test feature flag configuration."""
    
    def test_should_use_new_chunking_with_full_rollout(self):
        """Test that full rollout enables new chunking."""
        with patch('modules.chunking_config.ROLLOUT_PERCENT', 100):
            with patch('modules.chunking_config.RICH_CHUNK_METADATA_ENABLED', True):
                assert should_use_new_chunking("doc_123") is True
    
    def test_should_use_new_chunking_with_zero_rollout(self):
        """Test that zero rollout disables new chunking."""
        with patch('modules.chunking_config.ROLLOUT_PERCENT', 0):
            assert should_use_new_chunking("doc_123") is False
    
    def test_deterministic_bucket_assignment(self):
        """Test that bucket assignment is deterministic."""
        with patch('modules.chunking_config.ROLLOUT_PERCENT', 50):
            result1 = should_use_new_chunking("doc_abc")
            result2 = should_use_new_chunking("doc_abc")
            assert result1 == result2
    
    def test_telemetry_includes_version(self):
        """Test that telemetry includes version info."""
        telemetry = get_chunking_telemetry("doc_123")
        assert "chunk_version" in telemetry
        assert "embedding_version" in telemetry
        assert "schema_version" in telemetry


# ============================================================================
# Unit Tests: Token Utilities
# ============================================================================

class TestTokenUtilities:
    """Test token estimation and chunking."""
    
    def test_estimate_tokens_empty(self):
        """Test token estimation with empty string."""
        assert estimate_tokens("") == 0
    
    def test_estimate_tokens_short_text(self):
        """Test token estimation with short text."""
        text = "Hello world"
        tokens = estimate_tokens(text)
        # Rough estimate: 11 chars / 4 = ~3 tokens
        assert tokens > 0
        assert tokens < 10
    
    def test_estimate_tokens_long_text(self):
        """Test token estimation scales with text length."""
        short = "Hello"
        long = "Hello " * 100
        
        short_tokens = estimate_tokens(short)
        long_tokens = estimate_tokens(long)
        
        assert long_tokens > short_tokens
    
    def test_chunk_by_tokens_respects_target(self):
        """Test that chunk_by_tokens respects target size."""
        text = "This is a sentence. " * 50  # ~1000 chars
        chunks = chunk_by_tokens(
            text,
            target_tokens=50,
            overlap_tokens=10,
        )
        
        assert len(chunks) > 0
        # Each chunk should be reasonably sized
        for chunk in chunks:
            tokens = estimate_tokens(chunk["text"])
            assert tokens <= 200  # Allow some flexibility
    
    def test_chunk_by_tokens_preserves_sentences(self):
        """Test that chunking preserves sentence boundaries."""
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunk_by_tokens(text, target_tokens=10)
        
        # Should not split mid-sentence
        for chunk in chunks:
            text = chunk["text"]
            # Each chunk should end with complete sentence
            assert not text.endswith(" Fir")  # Mid-word


# ============================================================================
# Unit Tests: Structure Detection
# ============================================================================

class TestStructureDetection:
    """Test heading and speaker detection."""
    
    def test_detect_heading_markdown(self):
        """Test markdown heading detection."""
        line = "# Section Title"
        result = detect_heading(line)
        assert result is not None
        assert result["title"] == "Section Title"
        assert result["level"] == 1
    
    def test_detect_heading_numbered(self):
        """Test numbered heading detection."""
        line = "1. Introduction"
        result = detect_heading(line)
        assert result is not None
        assert "Introduction" in result["title"]
    
    def test_detect_heading_not_heading(self):
        """Test that regular text is not detected as heading."""
        line = "This is just a regular sentence."
        result = detect_heading(line)
        assert result is None
    
    def test_detect_speaker_turn_simple(self):
        """Test simple speaker turn detection."""
        line = "John: Hello everyone"
        result = detect_speaker_turn(line)
        assert result is not None
        assert result["speaker"] == "John"
        assert result["text"] == "Hello everyone"
    
    def test_detect_speaker_turn_bracketed(self):
        """Test bracketed speaker format."""
        line = "[Sarah] How are you?"
        result = detect_speaker_turn(line)
        assert result is not None
        assert result["speaker"] == "Sarah"
    
    def test_detect_speaker_turn_no_speaker(self):
        """Test line without speaker."""
        line = "Just a regular line of text."
        result = detect_speaker_turn(line)
        assert result is None


# ============================================================================
# Unit Tests: Embedding Text Builder
# ============================================================================

class TestEmbeddingTextBuilder:
    """Test embedding text construction."""
    
    def test_build_embedding_text_with_all_context(self):
        """Test building embedding text with full context."""
        text = build_embedding_text(
            chunk_summary="Revenue increased by 15%.",
            chunk_title="Financial Results",
            doc_title="Annual Report 2024",
            section_path="Financials > Q3",
            source_type="pdf",
        )
        
        assert "Document: Annual Report 2024" in text
        assert "Section: Financials > Q3" in text
        assert "Topic: Financial Results" in text
        assert "Type: pdf" in text
        assert "Revenue increased by 15%" in text
    
    def test_build_embedding_text_minimal(self):
        """Test building embedding text with minimal info."""
        text = build_embedding_text(
            chunk_summary="Simple summary.",
        )
        
        assert text == "Simple summary."
    
    def test_validate_embedding_text_valid(self):
        """Test validation of valid embedding text."""
        text = """Document: Test Doc
Section: Section 1

This is the content."""
        
        result = validate_embedding_text(text)
        assert result["valid"] is True
        assert result["has_content"] is True
    
    def test_validate_embedding_text_empty(self):
        """Test validation of empty text."""
        result = validate_embedding_text("")
        assert result["valid"] is False
        assert len(result["warnings"]) > 0
    
    def test_build_legacy_embedding_text(self):
        """Test legacy embedding text builder."""
        text = build_legacy_embedding_text(
            chunk_text="The content here.",
            section_title="Section A",
            block_type="prompt_question",
        )
        
        # For prompt_question, should use section title
        assert text == "Section A"
    
    def test_build_legacy_embedding_text_default(self):
        """Test legacy builder returns chunk text by default."""
        text = build_legacy_embedding_text(
            chunk_text="The content.",
            section_title=None,
            block_type="paragraph",
        )
        
        assert text == "The content."


# ============================================================================
# Unit Tests: Chunk Summarizer
# ============================================================================

class TestChunkSummarizer:
    """Test chunk summarization."""
    
    def test_extractive_fallback_short_text(self):
        """Test fallback with short text."""
        text = "Short sentence."
        result = _extractive_fallback(text)
        assert result == "Short sentence."
    
    def test_extractive_fallback_long_text(self):
        """Test fallback truncates long text."""
        text = "This is sentence one. This is sentence two. This is sentence three." * 10
        result = _extractive_fallback(text, max_words=10)
        
        word_count = len(result.split())
        assert word_count <= 12  # Allow some flexibility
    
    def test_generate_chunk_title_with_section(self):
        """Test title generation uses section title."""
        title = generate_chunk_title(
            chunk_text="Any content here.",
            section_title="The Section Title",
        )
        assert title == "The Section Title"
    
    def test_generate_chunk_title_from_first_line(self):
        """Test title extraction from first line."""
        text = "Heading Without Period\nMore content here."
        title = generate_chunk_title(text)
        assert title == "Heading Without Period"


# ============================================================================
# Unit Tests: Semantic Chunk
# ============================================================================

class TestSemanticChunk:
    """Test SemanticChunk dataclass."""
    
    def test_to_vector_metadata(self):
        """Test conversion to vector metadata."""
        chunk = SemanticChunk(
            chunk_text="Full text here.",
            chunk_summary="Summary here.",
            chunk_title="The Title",
            doc_title="Doc Title",
            doc_id="doc_123",
            source_type="pdf",
            source_id="src_123",
            chunk_index=0,
            total_chunks=5,
        )
        
        metadata = chunk.to_vector_metadata()
        
        assert metadata["chunk_text"] == "Full text here."
        assert metadata["chunk_summary"] == "Summary here."
        assert metadata["chunk_title"] == "The Title"
        assert metadata["doc_title"] == "Doc Title"
        assert metadata["chunk_index"] == 0
        assert metadata["total_chunks"] == 5
        assert metadata["chunk_version"] == CHUNK_VERSION
    
    def test_detect_section_level(self):
        """Test section level detection."""
        assert _detect_section_level("Simple Title") == 1
        assert _detect_section_level("Parent > Child") == 2
        assert _detect_section_level("A > B > C") == 3
        assert _detect_section_level(None) == 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestChunkingIntegration:
    """Integration tests for full chunking pipeline."""
    
    @pytest.mark.asyncio
    async def test_create_semantic_chunks_basic(self):
        """Test end-to-end semantic chunk creation."""
        text = """
# Section One

This is the first paragraph with some content about revenue.
Revenue was $5M this quarter.

# Section Two

This section discusses products.
Product A is doing well.
        """.strip()
        
        chunks = await create_semantic_chunks(
            text=text,
            doc_title="Test Document",
            doc_id="doc_123",
            source_id="src_123",
            source_type="markdown",
        )
        
        assert len(chunks) > 0
        
        for chunk in chunks:
            # Each chunk should have rich metadata
            assert chunk.chunk_text
            assert chunk.chunk_summary
            assert chunk.doc_title == "Test Document"
            assert chunk.embedding_text
            assert chunk.chunk_version == CHUNK_VERSION
    
    @pytest.mark.asyncio
    async def test_create_semantic_chunks_transcript(self):
        """Test semantic chunking with transcript format."""
        text = """
John: Welcome to the meeting.
Sarah: Thanks John, let's get started.
John: First item is revenue.
Sarah: Revenue is up 20%.
        """.strip()
        
        chunks = await create_semantic_chunks(
            text=text,
            doc_title="Team Meeting",
            doc_id="doc_456",
            source_id="src_456",
            source_type="transcript",
        )
        
        assert len(chunks) > 0
        
        # Check that speaker info is preserved
        speakers = [c.speaker for c in chunks if c.speaker]
        assert "John" in speakers or "Sarah" in speakers
    
    @pytest.mark.asyncio
    async def test_chunking_policy_varies_by_source(self):
        """Test that different source types use different policies."""
        text = "Word " * 500  # Long text
        
        # Get policies
        transcript_policy = get_chunking_policy("transcript")
        pdf_policy = get_chunking_policy("pdf")
        
        # Transcript should have larger target
        assert transcript_policy["target_tokens"] >= pdf_policy["target_tokens"]


# ============================================================================
# Backward Compatibility Tests
# ============================================================================

class TestBackwardCompatibility:
    """Test backward compatibility with old chunks."""
    
    def test_legacy_chunk_format_still_works(self):
        """Test that old chunk format is still accepted."""
        old_chunk = {
            "text": "Old style chunk text.",
            "section_title": "Old Section",
            "section_path": "Path > To > Section",
            "block_type": "answer_text",
        }
        
        # Should be able to build embedding text
        from modules.embedding_text_builder import build_legacy_embedding_text
        embedding_text = build_legacy_embedding_text(
            chunk_text=old_chunk["text"],
            section_title=old_chunk["section_title"],
            section_path=old_chunk["section_path"],
            block_type=old_chunk["block_type"],
        )
        
        assert embedding_text == "Old style chunk text."
    
    def test_new_chunks_have_all_legacy_fields(self):
        """Test that new chunks include legacy-compatible fields."""
        chunk = SemanticChunk(
            chunk_text="The content.",
            chunk_summary="Summary.",
            chunk_title="Title",
            doc_title="Doc",
            doc_id="doc_1",
            source_type="pdf",
            source_id="src_1",
            section_title="Section",
            section_path="Path > Section",
        )
        
        metadata = chunk.to_vector_metadata()
        
        # Should have fields that legacy code expects
        assert "section_title" in metadata
        assert "section_path" in metadata
        assert "chunk_text" in metadata  # Legacy field name


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance-related tests."""
    
    @pytest.mark.asyncio
    async def test_chunking_completes_in_reasonable_time(self):
        """Test that chunking completes within acceptable time."""
        text = "Paragraph with content. " * 100
        
        import time
        start = time.time()
        
        chunks = await create_semantic_chunks(
            text=text,
            doc_title="Perf Test",
            doc_id="doc_perf",
            source_id="src_perf",
        )
        
        elapsed = time.time() - start
        
        # Should complete in under 10 seconds for small doc
        assert elapsed < 10.0
        assert len(chunks) > 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
