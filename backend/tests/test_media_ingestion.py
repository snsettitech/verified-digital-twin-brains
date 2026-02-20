import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def media_ingestion_module():
    """Load media_ingestion with mocked dependencies to keep tests deterministic."""
    mock_observability = MagicMock()
    mock_observability.supabase = MagicMock()
    mock_observability.log_ingestion_event = MagicMock()

    mock_ingestion = MagicMock()
    mock_ingestion.process_and_index_text = AsyncMock(return_value=5)

    mock_clients = MagicMock()
    mock_clients.get_openai_client = MagicMock(return_value=MagicMock())

    with patch.dict(
        sys.modules,
        {
            "modules.observability": mock_observability,
            "modules.ingestion": mock_ingestion,
            "modules.auth_guard": MagicMock(),
            "modules.clients": mock_clients,
            "modules.governance": MagicMock(),
        },
        clear=False,
    ):
        sys.modules.pop("modules.media_ingestion", None)
        module = importlib.import_module("modules.media_ingestion")
        yield module, mock_ingestion, mock_clients
        sys.modules.pop("modules.media_ingestion", None)


@pytest.mark.asyncio
async def test_ingest_youtube_success(media_ingestion_module):
    """YouTube ingestion returns success and awaits indexing pipeline."""
    module, mock_ingestion, _ = media_ingestion_module
    MediaIngester = module.MediaIngester

    with (
        patch.object(MediaIngester, "_download_audio", return_value="fake.mp3"),
        patch.object(MediaIngester, "_transcribe_audio", new=AsyncMock(return_value="Raw transcript")),
        patch.object(MediaIngester, "_diarize_and_process", new=AsyncMock(return_value="Diarized content")),
    ):
        ingester = MediaIngester("twin-123")
        result = await ingester.ingest_youtube_video("http://youtube.com/watch?v=123")

    assert result["success"] is True
    assert result["chunks"] == 5
    assert mock_ingestion.process_and_index_text.await_count == 1


@pytest.mark.asyncio
async def test_diarization_logic(media_ingestion_module):
    """Diarization awaits LLM completion and returns extracted content."""
    module, _, mock_clients = media_ingestion_module

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Diarized text"))]

    mock_openai_client = MagicMock()
    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_clients.get_openai_client.return_value = mock_openai_client

    ingester = module.MediaIngester("twin-123")
    result = await ingester._diarize_and_process("Full raw text")

    assert result == "Diarized text"
    assert mock_openai_client.chat.completions.create.await_count == 1
