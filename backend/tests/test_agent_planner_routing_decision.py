import pytest
from langchain_core.messages import HumanMessage
from unittest.mock import AsyncMock

from modules.agent import planner_node


@pytest.mark.asyncio
async def test_planner_non_answerable_emits_targeted_clarifications(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "insufficient",
                "confidence": 0.22,
                "reasoning": "Evidence does not include budget limits or success criteria.",
                "missing_information": ["the budget ceiling for this plan", "the success metric to optimize for"],
                "ambiguity_level": "high",
            }
        ),
    )

    state = {
        "messages": [HumanMessage(content="Create a rollout plan")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": [{"text": "Use phased rollout.", "source_id": "src-1"}]},
        "routing_decision": {"intent": "plan", "chosen_workflow": "plan", "output_schema": "workflow.plan.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    planning = out["planning_output"]

    assert planning["render_strategy"] == "source_faithful"
    assert planning["answer_points"][0].startswith("I don't know based on available sources")
    assert len(planning["teaching_questions"]) <= 3
    assert any("budget" in q.lower() for q in planning["teaching_questions"])
    assert "what outcome do you want from this conversation" not in " ".join(planning["teaching_questions"]).lower()
    assert out["routing_decision"]["action"] == "clarify"


@pytest.mark.asyncio
async def test_planner_derivable_answers_without_i_dont_know(monkeypatch):
    monkeypatch.setattr(
        "modules.agent.build_system_prompt_with_trace",
        lambda _state: (
            "system",
            {
                "intent_label": "factual_with_evidence",
                "module_ids": [],
                "persona_spec_version": "1.0.0",
                "persona_prompt_variant": "baseline_v1",
            },
        ),
    )
    monkeypatch.setattr(
        "modules.agent.evaluate_answerability",
        AsyncMock(
            return_value={
                "answerability": "derivable",
                "confidence": 0.67,
                "reasoning": "Answer is derivable by combining setup chunks.",
                "missing_information": [],
                "ambiguity_level": "medium",
            }
        ),
    )
    monkeypatch.setattr("modules.agent.invoke_json", AsyncMock(side_effect=RuntimeError("planner unavailable")))

    state = {
        "messages": [HumanMessage(content="How to use the twin?")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {
            "results": [
                {"text": "Use onboarding and review workflow.", "source_id": "src-1"},
                {"text": "Twin operation starts by connecting sources.", "source_id": "src-2"},
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
        "reasoning_history": [],
    }

    out = await planner_node(state)
    planning = out["planning_output"]

    assert out["routing_decision"]["action"] == "answer"
    assert planning["teaching_questions"] == []
    assert "i don't know" not in " ".join(planning["answer_points"]).lower()
