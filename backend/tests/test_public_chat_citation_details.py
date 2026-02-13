from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from main import app


client = TestClient(app)


async def _fake_agent_stream(*_args, **_kwargs):
    yield {"tools": {"citations": ["src-1"], "confidence_score": 0.9}}
    yield {"agent": {"messages": [AIMessage(content="Public cited answer.")]}}


def test_public_chat_returns_citation_details_and_confidence():
    with patch("routers.chat.ensure_twin_active"), patch(
        "modules.share_links.validate_share_token", return_value=True
    ), patch(
        "modules.share_links.get_public_group_for_twin", return_value={"id": "group-public"}
    ), patch(
        "modules.rate_limiting.check_rate_limit", return_value=(True, {})
    ), patch(
        "modules.actions_engine.EventEmitter.emit", return_value=None
    ), patch(
        "routers.chat.run_identity_gate",
        new=AsyncMock(
            return_value={
                "decision": "ANSWER",
                "owner_memory_context": "",
                "owner_memory_refs": [],
                "owner_memory": [],
            }
        ),
    ), patch(
        "routers.chat.run_agent_stream", _fake_agent_stream
    ), patch(
        "routers.chat.log_interaction"
    ), patch(
        "routers.chat._resolve_citation_details",
        return_value=[
            {"id": "src-1", "filename": "source.txt", "citation_url": "https://example.com/source.txt"}
        ],
    ):
        response = client.post(
            "/public/chat/twin-1/token-abc12345",
            json={"message": "What is your stance?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["response"] == "Public cited answer."
        assert payload["citations"] == ["src-1"]
        assert payload["confidence_score"] == 0.9
        assert payload["citation_details"][0]["filename"] == "source.txt"
