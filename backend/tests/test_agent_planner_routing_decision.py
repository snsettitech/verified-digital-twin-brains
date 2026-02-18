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
                "answerable": False,
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
