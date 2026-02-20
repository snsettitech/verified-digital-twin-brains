from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node
from modules.response_composer import compose_answer_points


def test_compose_answer_points_filters_prompt_like_lines_for_non_quote():
    result = compose_answer_points(
        query="Tell me about yourself",
        query_class="identity",
        quote_intent=False,
        planner_points=[
            "1) Who are you (short bio used in the twin)",
            "I am a pragmatic operator focused on fast decisions.",
        ],
        context_data=[],
        max_points=3,
    )

    assert result["points"]
    assert all(not point.strip().startswith("1)") for point in result["points"])
    assert all(not point.strip().endswith("?") for point in result["points"])


def test_compose_answer_points_identity_template_labels():
    result = compose_answer_points(
        query="who are you",
        query_class="identity",
        quote_intent=False,
        planner_points=["I am focused on founder outcomes and execution speed."],
        context_data=[],
        max_points=3,
    )

    assert result["points"][0].startswith("Who I am:")


@pytest.mark.asyncio
async def test_planner_node_blocks_questionnaire_dump_in_non_quote_turn(monkeypatch):
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
                "answerability": "direct",
                "confidence": 0.86,
                "reasoning": "Answerable from identity evidence.",
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
                        "1) Who are you (short bio used in the twin)",
                        "2) What are your core expertise areas?",
                    ],
                    "citations": ["src-identity"],
                    "confidence": 0.84,
                    "reasoning_trace": "Bad planner draft with prompt lines.",
                },
                {"provider": "test"},
            )
        ),
    )

    state = {
        "messages": [HumanMessage(content="Tell me about yourself")],
        "dialogue_mode": "QA_FACT",
        "query_class": "identity",
        "quote_intent": False,
        "retrieved_context": {
            "results": [
                {
                    "source_id": "src-identity",
                    "text": "I am a pragmatic operator focused on founder outcomes.",
                    "block_type": "answer_text",
                    "is_answer_text": True,
                }
            ]
        },
        "routing_decision": {"intent": "answer", "chosen_workflow": "answer", "output_schema": "workflow.answer.v1"},
    }

    out = await planner_node(state)
    answer_points = out["planning_output"]["answer_points"]

    assert answer_points
    assert all(not point.strip().startswith("1)") for point in answer_points)
    assert all("who are you" not in point.lower() for point in answer_points)
    assert any("who i am:" in point.lower() for point in answer_points)
