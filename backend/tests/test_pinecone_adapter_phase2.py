from unittest.mock import MagicMock

import pytest

from modules.pinecone_adapter import PineconeIndexAdapter


def test_adapter_mode_defaults_to_vector(monkeypatch):
    monkeypatch.delenv("PINECONE_INDEX_MODE", raising=False)
    monkeypatch.delenv("PINECONE_HOST", raising=False)

    adapter = PineconeIndexAdapter(MagicMock())

    assert adapter.mode == "vector"
    assert adapter.host_override is False


def test_vector_mode_upsert_and_query_passthrough(monkeypatch):
    monkeypatch.setenv("PINECONE_INDEX_MODE", "vector")

    mock_index = MagicMock()
    mock_query_response = {
        "matches": [
            {
                "id": "vec-1",
                "score": 0.91,
                "metadata": {"text": "hello", "source_id": "src-1"},
            }
        ]
    }
    mock_index.query.return_value = mock_query_response

    adapter = PineconeIndexAdapter(mock_index)

    vectors = [
        {
            "id": "vec-1",
            "values": [0.1, 0.2],
            "metadata": {"text": "hello", "source_id": "src-1"},
        }
    ]
    adapter.upsert(vectors=vectors, namespace="creator_a_twin_b")
    mock_index.upsert.assert_called_once_with(vectors=vectors, namespace="creator_a_twin_b")

    result = adapter.query(
        vector=[0.1, 0.2],
        query_text="ignored in vector mode",
        top_k=8,
        namespace="creator_a_twin_b",
        include_metadata=True,
        metadata_filter={"twin_id": {"$eq": "b"}},
    )
    mock_index.query.assert_called_once_with(
        vector=[0.1, 0.2],
        top_k=8,
        include_metadata=True,
        namespace="creator_a_twin_b",
        filter={"twin_id": {"$eq": "b"}},
    )
    assert result == mock_query_response


def test_vector_mode_upsert_strips_null_metadata(monkeypatch):
    monkeypatch.setenv("PINECONE_INDEX_MODE", "vector")

    mock_index = MagicMock()
    adapter = PineconeIndexAdapter(mock_index)

    vectors = [
        {
            "id": "vec-1",
            "values": [0.1, 0.2],
            "metadata": {
                "text": "hello",
                "source_id": "src-1",
                "tombstoned_at": None,
                "nested": {"keep": "yes", "drop": None},
                "tags": ["a", None, "b"],
            },
        }
    ]

    adapter.upsert(vectors=vectors, namespace="creator_a_twin_b")

    upsert_payload = mock_index.upsert.call_args.kwargs["vectors"]
    assert upsert_payload[0]["metadata"] == {
        "text": "hello",
        "source_id": "src-1",
        "nested": {"keep": "yes"},
        "tags": ["a", "b"],
    }


def test_integrated_mode_requires_text_field(monkeypatch):
    monkeypatch.setenv("PINECONE_INDEX_MODE", "integrated")
    monkeypatch.setenv("PINECONE_TEXT_FIELD", "")

    mock_index = MagicMock()
    mock_index.upsert_records = MagicMock()
    mock_index.search_records = MagicMock()

    with pytest.raises(ValueError, match="PINECONE_TEXT_FIELD"):
        PineconeIndexAdapter(mock_index)
