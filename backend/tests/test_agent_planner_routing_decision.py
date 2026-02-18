import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node


@pytest.mark.asyncio
async def test_planner_honors_clarify_routing_decision(monkeypatch):
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

    state = {
        "messages": [HumanMessage(content="Plan this for me")],
        "dialogue_mode": "QA_FACT",
        "retrieved_context": {"results": []},
        "target_owner_scope": False,
        "routing_decision": {
            "intent": "plan",
            "confidence": 0.41,
            "required_inputs_missing": ["objective", "constraints"],
            "chosen_workflow": "plan",
            "output_schema": "workflow.plan.v1",
            "action": "clarify",
            "clarifying_questions": [
                "What outcome do you want?",
                "What constraints should I respect?",
            ],
        },
        "reasoning_history": [],
    }

    out = await planner_node(state)
    planning = out["planning_output"]
    assert planning["render_strategy"] == "source_faithful"
    assert planning["workflow"] == "plan"
    assert planning["output_schema"] == "workflow.plan.v1"
    assert planning["teaching_questions"] == [
        "What outcome do you want?",
        "What constraints should I respect?",
    ]

