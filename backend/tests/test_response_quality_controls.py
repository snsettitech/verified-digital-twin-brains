import pytest
from langchain_core.messages import HumanMessage


def test_build_system_prompt_includes_override(monkeypatch):
    from modules.agent import build_system_prompt

    class DummyRpcResponse:
        data = []

    class DummySupabase:
        def rpc(self, *args, **kwargs):
            return DummyRpcResponse()

    monkeypatch.setattr("modules.agent.supabase", DummySupabase())

    state = {
        "twin_id": "twin-123",
        "full_settings": {},
        "graph_context": "",
        "owner_memory_context": "",
        "system_prompt_override": "Always answer in haiku."
    }

    prompt = build_system_prompt(state)
    assert "Always answer in haiku." in prompt


@pytest.mark.asyncio
async def test_evidence_gate_requires_teaching_on_empty_context():
    from modules.agent import evidence_gate_node

    state = {
        "dialogue_mode": "QA_FACT",
        "target_owner_scope": True,
        "retrieved_context": {"results": []},
        "messages": [HumanMessage(content="Where did I grow up?")],
        "requires_evidence": True,
        "reasoning_history": []
    }

    result = await evidence_gate_node(state)
    assert result["dialogue_mode"] == "TEACHING"
    assert result["requires_teaching"] is True


@pytest.mark.asyncio
async def test_retrieval_tool_uses_history_for_expansion(monkeypatch):
    from modules.tools import get_retrieval_tool

    captured = {}

    async def fake_retrieve_context(query, twin_id, group_id=None, top_k=5):
        captured["query"] = query
        return []

    monkeypatch.setattr("modules.tools.retrieve_context", fake_retrieve_context)

    history = [HumanMessage(content="We discussed the M&A reflection for SGMT 6050 earlier.")]
    tool = get_retrieval_tool("twin-123", conversation_history=history)

    await tool.ainvoke({"query": "reflection"})
    assert captured.get("query") != "reflection"
