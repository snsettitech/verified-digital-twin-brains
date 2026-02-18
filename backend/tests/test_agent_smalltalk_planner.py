from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node, realizer_node


def _trace():
    return (
        "system",
        {
            "intent_label": "factual_with_evidence",
            "module_ids": [],
            "persona_spec_version": "1.0.0",
            "persona_prompt_variant": "baseline_v1",
        },
    )


@pytest.mark.asyncio
async def test_explicit_recommendation_no_clarifications(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "direct",
                "confidence": 0.92,
                "reasoning": "Recommendation is explicitly stated.",
                "missing_information": [],
                "ambiguity_level": "low",
            }
        ),
    )
    monkeypatch.setattr(
        "modules.agent.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answer_points": [
                        "Recommendation: Start with containers on a managed platform.",
                        "Why: It reduces operational debugging friction for MVP.",
                    ],
                    "citations": ["src-1"],
                    "confidence": 0.9,
                    "reasoning_trace": "Grounded recommendation extracted.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="Should we use containers or serverless for MVP?")],
        "retrieved_context": {"results": [{"source_id": "src-1", "text": "Recommendation: Start with containers."}]},
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["citations"] == ["src-1"]
    assert plan["teaching_questions"] == []
    assert plan["follow_up_question"] == ""
    assert all(not p.strip().endswith("?") for p in plan["answer_points"])


@pytest.mark.asyncio
async def test_missing_constraints_produces_targeted_clarifications(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.2,
                "reasoning": "Constraints are missing.",
                "missing_information": [
                    "the budget ceiling for implementation",
                    "the deadline for MVP launch",
                ],
                "ambiguity_level": "high",
            }
        ),
    )
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=AssertionError("should not compose answer")))

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="Give me an implementation plan")],
        "retrieved_context": {"results": [{"source_id": "src-1", "text": "Use phased rollout."}]},
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert plan["answer_points"][0].startswith("I don't know based on available sources")
    assert 1 <= len(plan["teaching_questions"]) <= 3
    assert any("budget" in q.lower() for q in plan["teaching_questions"])
    assert "what outcome do you want from this conversation" not in " ".join(plan["teaching_questions"]).lower()


@pytest.mark.asyncio
async def test_identity_question_answered_if_evidence_exists(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "direct",
                "confidence": 0.88,
                "reasoning": "Identity details are explicit in evidence.",
                "missing_information": [],
                "ambiguity_level": "low",
            }
        ),
    )
    monkeypatch.setattr(
        "modules.agent.invoke_json",
        AsyncMock(
            return_value=(
                {
                    "answer_points": [
                        "I am Sainath Setti.",
                        "I focus on cloud reliability and AI system design.",
                    ],
                    "citations": ["src-identity"],
                    "confidence": 0.86,
                    "reasoning_trace": "Identity statements grounded in source.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "dialogue_mode": "QA_FACT",
        "messages": [HumanMessage(content="Who are you?")],
        "retrieved_context": {
            "results": [
                {"source_id": "src-identity", "text": "I am Sainath Setti. I focus on cloud reliability and AI."}
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
    }

    result = await planner_node(state)
    plan = result["planning_output"]
    assert "Sainath" in " ".join(plan["answer_points"])
    assert plan["teaching_questions"] == []
    assert plan["citations"] == ["src-identity"]


@pytest.mark.asyncio
async def test_realizer_source_faithful_remains_deterministic():
    state = {
        "dialogue_mode": "QA_FACT",
        "planning_output": {
            "answer_points": [
                "Recommendation: Start with containers.",
                "Why: Faster debugging during MVP.",
            ],
            "citations": ["src-1"],
            "follow_up_question": "",
            "teaching_questions": [],
            "render_strategy": "source_faithful",
        },
        "intent_label": "factual_with_evidence",
        "persona_module_ids": [],
    }

    result = await realizer_node(state)
    msg = result["messages"][0]
    assert "Recommendation:" in msg.content
    assert msg.additional_kwargs.get("render_strategy") == "source_faithful"
