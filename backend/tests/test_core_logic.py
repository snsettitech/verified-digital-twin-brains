import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.mark.asyncio
@pytest.mark.network  # Skip in CI - requires real network services
async def test_retrieve_context_structure():
    """Test retrieval context structure - requires network access to services."""
    # This test makes network calls during module import
    # Skipped in CI with pytest -m "not network"
    from modules.retrieval import retrieve_context
    
    # Mock Pinecone index
    mock_index = MagicMock()
    mock_index.query.return_value = {
        "matches": [
            {
                "score": 0.9,
                "metadata": {"text": "This is a test chunk", "source_id": "src-123"}
            }
        ]
    }
    
    with patch("modules.retrieval.get_pinecone_index", return_value=mock_index), \
         patch("modules.retrieval.get_embedding", return_value=[0.1]*3072), \
         patch("modules.retrieval.expand_query", return_value=["query var"]), \
         patch("modules.retrieval.generate_hyde_answer", return_value="hyde answer"), \
         patch("modules.retrieval.get_embeddings_async", return_value=[[0.1]*3072]*3), \
         patch("modules.retrieval.get_ranker", return_value=None), \
         patch("modules.retrieval.get_default_group", new_callable=AsyncMock, side_effect=ValueError("no default group")), \
         patch("modules.retrieval.match_verified_qna", new_callable=AsyncMock, return_value=None):
        
        results = await retrieve_context("test query", "twin-456")
        
        assert len(results) == 1
        assert results[0]["text"] == "This is a test chunk"
        # Retrieval now applies reranker + lexical fusion; score is normalized, not hard-1.0.
        assert 0.0 < float(results[0]["score"]) <= 1.0
        assert results[0]["source_id"] == "src-123"
        assert results[0]["is_verified"] == True


@pytest.mark.network  # Skip in CI - requires real network services
def test_generate_answer_citations():
    """Test answer generation with citations - requires network access."""
    from modules.answering import generate_answer
    
    mock_contexts = [
        {"text": "Sample knowledge", "score": 0.8, "source_id": "src-1"}
    ]
    
    mock_openai_response = MagicMock()
    mock_openai_response.choices[0].message.content = "The answer is here [Source 1]"
    
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_openai_response
    
    with patch("modules.answering.get_openai_client", return_value=mock_client):
        result = generate_answer("test query", mock_contexts)
        
        assert "answer" in result
        assert "[Source 1]" in result["answer"]
        assert result["confidence_score"] == 0.8
        assert result["citations"] == ["src-1"]
