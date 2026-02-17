import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node
from modules.response_policy import UNCERTAINTY_RESPONSE


@pytest.mark.asyncio
async def test_planner_smalltalk_identity_uses_public_intro():
    state = {
        "dialogue_mode": "SMALLTALK",
        "messages": [HumanMessage(content="who are you?")],
        "retrieved_context": {"results": []},
        "full_settings": {"public_intro": "I am Shambhavi, a VC partner focused on founder coaching."},
        "intent_label": "meta_or_system",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"]
    assert "Shambhavi" in plan["answer_points"][0]
    assert plan["citations"] == []


@pytest.mark.asyncio
async def test_planner_smalltalk_greeting_has_default_answer():
    state = {
        "dialogue_mode": "SMALLTALK",
        "messages": [HumanMessage(content="hi")],
        "retrieved_context": {"results": []},
        "full_settings": {},
        "intent_label": "meta_or_system",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"]
    assert "Hi there" in plan["answer_points"][0]
    assert plan["citations"] == []


@pytest.mark.asyncio
async def test_planner_generic_no_evidence_uses_general_fallback(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "factual_with_evidence", "module_ids": []})

    async def fake_invoke_text(*args, **kwargs):
        return "Antler is a global early-stage VC investor. Do you mean Antler the VC firm?", {"provider": "test"}

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)
    monkeypatch.setattr("modules.agent.invoke_text", fake_invoke_text)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="yes. i want to ask you about antler")],
        "retrieved_context": {"results": []},
        "target_owner_scope": False,
        "full_settings": {},
        "intent_label": "factual_with_evidence",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert "Antler" in plan["answer_points"][0]
    assert plan["citations"] == []
    assert plan["teaching_questions"] == []


@pytest.mark.asyncio
async def test_planner_owner_specific_no_evidence_returns_uncertainty_owner_chat(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "owner_position_request", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="What do I think about antler?")],
        "retrieved_context": {"results": []},
        "target_owner_scope": True,
        "interaction_context": "owner_chat",
        "full_settings": {},
        "intent_label": "owner_position_request",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"][0] == UNCERTAINTY_RESPONSE
    assert plan["teaching_questions"] == []
    assert plan["follow_up_question"] == ""


@pytest.mark.asyncio
async def test_planner_owner_specific_no_evidence_returns_teaching_prompts_in_training(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "owner_position_request", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "TEACHING",
        "messages": [HumanMessage(content="What do I think about antler?")],
        "retrieved_context": {"results": []},
        "target_owner_scope": True,
        "interaction_context": "owner_training",
        "full_settings": {},
        "intent_label": "owner_position_request",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"][0] == UNCERTAINTY_RESPONSE
    assert len(plan["teaching_questions"]) >= 1


@pytest.mark.asyncio
async def test_planner_comparison_query_extracts_recommendation_from_evidence(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "advice_or_stance", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="Should we use containers or serverless for our MVP?")],
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "text": (
                        "Recommendation: Start with containers on a managed platform.\n"
                        "Assumptions: Early-stage product, small team.\n"
                        "Why: Serverless can slow debugging in MVP mode."
                    ),
                }
            ]
        },
        "target_owner_scope": False,
        "full_settings": {},
        "intent_label": "advice_or_stance",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["citations"] == ["src-1"]
    assert any("Recommendation:" in point for point in plan["answer_points"])
    assert "comparison recommendation extracted" in plan["reasoning_trace"].lower()
