from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import HumanMessage

from modules.agent import planner_node, router_node
from modules.fastpath_intent_router import classify_fastpath_intent


def test_fastpath_intent_classifier_identity_and_fallback():
    hit = classify_fastpath_intent("Who are you?")
    miss = classify_fastpath_intent("Summarize this PDF in 3 bullets")

    assert hit["matched"] is True
    assert hit["intent"] == "identity_intro"
    assert hit["confidence"] > 0.9

    assert miss["matched"] is False
    assert miss["intent"] is None
    assert miss["confidence"] == 0.0


@pytest.mark.asyncio
async def test_fastpath_response_from_approved_profile(monkeypatch):
    with pytest.MonkeyPatch.context() as m:
        m.setenv("PERSONA_FASTPATH_ENABLED", "true")
        m.setenv("PERSONA_DRAFT_PROFILE_ALLOWED", "false")
        m.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)
        m.setattr(
            "modules.agent.get_persona_profile",
            lambda _twin_id: {
                "profile_status": "approved",
                "display_name": "Alex Rivera",
                "one_line_intro": "I help founders build AI products with practical GTM execution.",
                "short_intro": "I am a digital representation trained on Alex Rivera's public work.",
                "disclosure_line": "I’m an AI representation and not Alex directly.",
                "contact_handoff_line": "For direct contact, use the official channels.",
                "preferred_contact_channel": "linkedin",
                "social_links": {"linkedin": "https://linkedin.com/in/alex"},
                "expertise_areas": ["ai systems", "go-to-market"],
                "tone_tags": ["direct", "approachable"],
            },
        )

        routed = await router_node(
            {
                "twin_id": "twin-1",
                "messages": [HumanMessage(content="Who are you?")],
                "interaction_context": "owner_chat",
                "reasoning_history": [],
            }
        )
        assert routed["requires_evidence"] is False
        assert routed["fastpath_intent"] == "identity_intro"
        assert isinstance(routed["fastpath_response"], dict)
        assert routed["routing_decision"]["action"] == "answer"

        m.setattr(
            "modules.agent.evaluate_answerability",
            AsyncMock(side_effect=AssertionError("answerability should not run on fast-path")),
        )
        planned = await planner_node(
            {
                "messages": [HumanMessage(content="Who are you?")],
                "routing_decision": routed["routing_decision"],
                "reasoning_history": [],
                "fastpath_intent": routed["fastpath_intent"],
                "fastpath_response": routed["fastpath_response"],
            }
        )
        assert planned["planning_output"]["answer_points"]
        assert "founders" in planned["planning_output"]["answer_points"][0].lower()
        assert planned["planning_output"]["citations"] == []


@pytest.mark.asyncio
async def test_flags_off_keeps_existing_router_behavior(monkeypatch):
    with pytest.MonkeyPatch.context() as m:
        m.setenv("PERSONA_FASTPATH_ENABLED", "false")
        m.setenv("PERSONA_DRAFT_PROFILE_ALLOWED", "false")
        m.setattr("modules.agent._twin_has_groundable_knowledge", lambda _twin_id: True)

        out = await router_node(
            {
                "twin_id": "twin-1",
                "messages": [HumanMessage(content="Who are you?")],
                "interaction_context": "owner_chat",
                "reasoning_history": [],
            }
        )

        assert out["requires_evidence"] is True
        assert len(out["sub_queries"]) == 1
        assert out["fastpath_response"] is None
        assert out["fastpath_intent"] is None
