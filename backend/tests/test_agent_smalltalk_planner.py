import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node, realizer_node
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
    assert plan["render_strategy"] == "source_faithful"
    assert "comparison recommendation extracted" in plan["reasoning_trace"].lower()


@pytest.mark.asyncio
async def test_planner_comparison_query_unlabeled_evidence_uses_source_faithful(monkeypatch):
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
                        "For an early-stage product with a small team, containers on a managed platform "
                        "are easier to debug and iterate. Serverless can introduce cold starts and timeout "
                        "constraints during MVP development."
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
    assert plan["render_strategy"] == "source_faithful"
    assert any(point.startswith("Recommendation:") for point in plan["answer_points"])
    assert any(point.startswith("Assumptions:") for point in plan["answer_points"])
    assert any(point.startswith("Why:") for point in plan["answer_points"])
    assert any(
        point.startswith("Assumptions:") and ("early-stage" in point.lower() or "small team" in point.lower())
        for point in plan["answer_points"]
    )
    assert any(
        point.startswith("Why:") and ("cold start" in point.lower() or "timeout" in point.lower())
        for point in plan["answer_points"]
    )


@pytest.mark.asyncio
async def test_planner_high_confidence_evidence_uses_synthesis_path(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "factual_with_evidence", "module_ids": []})

    async def fake_invoke_json(*args, **kwargs):
        return (
            {
                "answer_points": ["Your incident response starts with stabilization, then status updates."],
                "citations": ["src-1"],
                "follow_up_question": "",
                "confidence": 0.9,
                "teaching_questions": [],
                "reasoning_trace": "planner-output",
            },
            {"provider": "test"},
        )

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)
    monkeypatch.setattr("modules.agent.invoke_json", fake_invoke_json)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="What is my incident response approach?")],
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "score": 0.82,
                    "text": (
                        "My incident response approach is to stabilize systems first, then communicate "
                        "status every 15 minutes until recovery. I run a blameless postmortem with clear "
                        "owners and due dates for follow-up actions."
                    ),
                }
            ]
        },
        "target_owner_scope": False,
        "full_settings": {},
        "intent_label": "factual_with_evidence",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["citations"] == ["src-1"]
    assert "render_strategy" not in plan
    assert "stabilization" in plan["answer_points"][0].lower()


@pytest.mark.asyncio
async def test_planner_mid_confidence_evidence_uses_source_faithful(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "factual_with_evidence", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="What is my incident response approach?")],
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "score": 0.71,
                    "text": (
                        "My incident response approach is to stabilize systems first, then communicate "
                        "status every 15 minutes until recovery. I run a blameless postmortem with clear "
                        "owners and due dates for follow-up actions."
                    ),
                }
            ]
        },
        "target_owner_scope": False,
        "full_settings": {},
        "intent_label": "factual_with_evidence",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["citations"] == ["src-1"]
    assert plan["render_strategy"] == "source_faithful"
    assert any("incident response" in point.lower() for point in plan["answer_points"])
    assert "adaptive grounding policy selected extractive" in plan["reasoning_trace"].lower()


@pytest.mark.asyncio
async def test_planner_low_confidence_owner_scope_forces_uncertainty(monkeypatch):
    def fake_prompt_builder(_state):
        return ("system", {"intent_label": "owner_position_request", "module_ids": []})

    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", fake_prompt_builder)

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="What is my stance on remote work?")],
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-1",
                    "score": 0.22,
                    "text": "Weekly team rituals include planning and demos.",
                }
            ]
        },
        "target_owner_scope": True,
        "full_settings": {},
        "intent_label": "owner_position_request",
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"][0] == UNCERTAINTY_RESPONSE
    assert "adaptive grounding policy blocked owner-specific synthesis" in plan["reasoning_trace"].lower()


@pytest.mark.asyncio
async def test_realizer_source_faithful_plan_avoids_paraphrase(monkeypatch):
    async def fail_invoke_text(*args, **kwargs):
        raise AssertionError("invoke_text should not be called in source_faithful mode")

    monkeypatch.setattr("modules.agent.invoke_text", fail_invoke_text)

    state = {
        "dialogue_mode": "QA_FACT",
        "planning_output": {
            "answer_points": [
                "Recommendation: Start with containers on a managed platform.",
                "Assumptions: Early-stage product, small team.",
                "Why: Serverless cold starts can slow MVP iteration.",
            ],
            "citations": ["src-1"],
            "follow_up_question": "",
            "teaching_questions": [],
            "render_strategy": "source_faithful",
        },
        "intent_label": "advice_or_stance",
        "persona_module_ids": [],
    }

    result = await realizer_node(state)
    msg = result["messages"][0]
    assert "Recommendation:" in msg.content
    assert "Assumptions:" in msg.content
    assert "Why:" in msg.content
    assert msg.additional_kwargs.get("render_strategy") == "source_faithful"
    assert result["citations"] == ["src-1"]
