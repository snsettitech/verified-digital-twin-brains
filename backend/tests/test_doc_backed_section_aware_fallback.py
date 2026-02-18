from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node


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
async def test_document_with_explicit_recommendation_has_no_clarifications(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerable": True,
                "confidence": 0.93,
                "reasoning": "Recommendation is explicit and complete.",
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
                    "answer_points": ["Recommendation: Start with containers on a managed platform."],
                    "citations": ["src-doc"],
                    "confidence": 0.91,
                    "reasoning_trace": "Grounded recommendation.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="Should we use containers or serverless for MVP?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-doc",
                    "text": "Recommendation: Start with containers on a managed platform.",
                }
            ]
        },
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
    }

    out = await planner_node(state)
    plan = out["planning_output"]
    assert plan["teaching_questions"] == []
    assert plan["follow_up_question"] == ""
    assert plan["citations"] == ["src-doc"]


@pytest.mark.asyncio
async def test_document_lacking_constraints_triggers_clarifications(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerable": False,
                "confidence": 0.18,
                "reasoning": "Constraints are not present in evidence.",
                "missing_information": ["the target budget", "the implementation deadline"],
                "ambiguity_level": "high",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="What rollout plan should we use?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": [{"source_id": "src-doc", "text": "Use staged rollout."}]},
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
    }

    out = await planner_node(state)
    plan = out["planning_output"]
    assert 1 <= len(plan["teaching_questions"]) <= 3
    assert any("budget" in q.lower() for q in plan["teaching_questions"])
    assert out["routing_decision"]["action"] == "clarify"


@pytest.mark.asyncio
async def test_identity_question_answered_directly_when_info_exists(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerable": True,
                "confidence": 0.87,
                "reasoning": "Identity info exists in evidence.",
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
                    "answer_points": ["I am Sainath Setti, focused on cloud reliability and AI systems."],
                    "citations": ["src-identity"],
                    "confidence": 0.86,
                    "reasoning_trace": "Identity evidence used.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="Who are you?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {"source_id": "src-identity", "text": "I am Sainath Setti. I work on cloud reliability and AI."}
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
    }

    out = await planner_node(state)
    plan = out["planning_output"]
    assert "Sainath" in plan["answer_points"][0]
    assert plan["teaching_questions"] == []


@pytest.mark.asyncio
async def test_random_manual_pdf_behaves_without_document_specific_config(monkeypatch):
    monkeypatch.setattr("modules.agent.build_system_prompt_with_trace", lambda _state: _trace())
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerable": True,
                "confidence": 0.8,
                "reasoning": "Manual contains direct installation steps.",
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
                    "answer_points": ["Set DIP switch 3 to ON, then reboot and verify green status LED."],
                    "citations": ["manual.pdf#p10"],
                    "confidence": 0.79,
                    "reasoning_trace": "Extracted from installation section.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="How do I enable maintenance mode on this controller?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {
                    "source_id": "manual.pdf#p10",
                    "text": "To enable maintenance mode: set DIP switch 3 to ON, reboot, and confirm green status LED.",
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
    }

    out = await planner_node(state)
    plan = out["planning_output"]
    assert plan["citations"] == ["manual.pdf#p10"]
    assert plan["teaching_questions"] == []
