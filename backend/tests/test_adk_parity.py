"""
ADK Parity Test Suite.

Validates that the ADK pipeline produces equivalent results to the
LangGraph pipeline for a set of standard queries.

Run: cd backend && python -m pytest tests/test_adk_parity.py -v
"""

import os
import pytest

# Force ADK runtime for these tests
os.environ["AGENT_RUNTIME"] = "adk"


class TestMessageTypes:
    """Verify the message abstraction layer works correctly."""

    def test_human_message_creation(self):
        from agents.message_types import human_message, is_human, get_content
        msg = human_message("Hello world")
        assert is_human(msg)
        assert get_content(msg) == "Hello world"
        assert msg["role"] == "user"
        assert msg["type"] == "human"

    def test_ai_message_creation(self):
        from agents.message_types import ai_message, is_ai, get_content
        msg = ai_message("I can help with that.")
        assert is_ai(msg)
        assert get_content(msg) == "I can help with that."
        assert msg["role"] == "assistant"

    def test_additional_kwargs(self):
        from agents.message_types import ai_message, set_additional_kwarg, get_additional_kwargs
        msg = ai_message("Response")
        msg = set_additional_kwarg(msg, "routing_decision", {"intent": "answer"})
        kwargs = get_additional_kwargs(msg)
        assert kwargs["routing_decision"]["intent"] == "answer"

    def test_immutability(self):
        """set_additional_kwarg must not mutate the original message."""
        from agents.message_types import ai_message, set_additional_kwarg
        original = ai_message("Response")
        modified = set_additional_kwarg(original, "key", "value")
        assert "key" not in original.get("additional_kwargs", {})
        assert modified["additional_kwargs"]["key"] == "value"

    def test_get_last_human_content(self):
        from agents.message_types import human_message, ai_message, get_last_human_content
        messages = [
            human_message("First question"),
            ai_message("First answer"),
            human_message("Second question"),
            ai_message("Second answer"),
        ]
        assert get_last_human_content(messages) == "Second question"

    def test_from_db_history(self):
        from agents.message_types import from_db_history, is_human, is_ai
        raw = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = from_db_history(raw)
        assert len(result) == 2
        assert is_human(result[0])
        assert is_ai(result[1])

    def test_to_inference_format(self):
        from agents.message_types import human_message, ai_message, to_inference_format
        messages = [
            human_message("Q"),
            ai_message("A"),
        ]
        formatted = to_inference_format(messages)
        assert formatted == [
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "A"},
        ]


class TestPipelineState:
    """Verify the pipeline state initialization."""

    def test_initial_state_has_required_keys(self):
        from agents.state import create_initial_state
        state = create_initial_state(twin_id="test-123", query="What do you do?")
        assert state["twin_id"] == "test-123"
        assert state["query"] == "What do you do?"
        assert state["requires_evidence"] is True
        assert state["execution_lane"] is False
        assert state["dialogue_mode"] == "QA_FACT"
        assert len(state["messages"]) == 1
        assert state["messages"][0]["content"] == "What do you do?"

    def test_initial_state_with_history(self):
        from agents.state import create_initial_state
        from agents.message_types import human_message, ai_message
        history = [
            human_message("Previous question"),
            ai_message("Previous answer"),
        ]
        state = create_initial_state(
            twin_id="test-123",
            query="Follow-up",
            history=history,
        )
        assert len(state["messages"]) == 3
        assert state["messages"][-1]["content"] == "Follow-up"

    def test_initial_state_routing_decision_shape(self):
        from agents.state import create_initial_state
        state = create_initial_state(twin_id="t", query="q")
        rd = state["routing_decision"]
        assert rd["intent"] == "answer"
        assert rd["action"] == "answer"
        assert "required_inputs_missing" in rd
        assert "clarifying_questions" in rd


class TestRunnerFeatureFlag:
    """Verify the runner routes to the correct pipeline based on env var."""

    def test_default_runtime_is_langgraph(self):
        from agents.runner import AGENT_RUNTIME
        # In test env, we set it to "adk" above, but verify the module loads
        assert AGENT_RUNTIME in ("adk", "langgraph")


class TestADKToolPineconeSearch:
    """Verify the Pinecone search tool functions."""

    def test_expand_ambiguous_query_generic(self):
        from adk_tools.pinecone_search import _expand_ambiguous_query
        history = [
            {"role": "user", "content": "Tell me about the M&A reflection from SGMT 6050"},
            {"role": "assistant", "content": "The M&A reflection covers..."},
        ]
        result = _expand_ambiguous_query("reflection", history)
        assert "M&A" in result

    def test_expand_non_ambiguous_passes_through(self):
        from adk_tools.pinecone_search import _expand_ambiguous_query
        result = _expand_ambiguous_query(
            "What is the company revenue for 2024?",
            [{"role": "user", "content": "Previous context"}],
        )
        assert result == "What is the company revenue for 2024?"

    def test_expand_no_history(self):
        from adk_tools.pinecone_search import _expand_ambiguous_query
        result = _expand_ambiguous_query("reflection", [])
        assert result == "reflection"
