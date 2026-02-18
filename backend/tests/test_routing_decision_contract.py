from modules.routing_decision import build_routing_decision


def test_routing_decision_contains_required_contract_fields():
    decision = build_routing_decision(
        query="Can you diagnose why activation dropped this week?",
        mode="QA_FACT",
        intent_label="factual_with_evidence",
        interaction_context="owner_chat",
        target_owner_scope=False,
        requires_evidence=True,
        knowledge_available=True,
        pinned_context={"problem_statement": "activation dropped", "context": "week-over-week"},
    )

    payload = decision.model_dump()
    assert set(payload.keys()) == {
        "intent",
        "confidence",
        "required_inputs_missing",
        "chosen_workflow",
        "output_schema",
        "action",
        "clarifying_questions",
    }
    assert payload["chosen_workflow"] == "diagnose"
    assert payload["output_schema"] == "workflow.diagnose.v1"


def test_routing_decision_clarifies_when_required_inputs_missing():
    decision = build_routing_decision(
        query="Can you plan this?",
        mode="QA_FACT",
        intent_label="advice_or_stance",
        interaction_context="owner_chat",
        target_owner_scope=False,
        requires_evidence=False,
        knowledge_available=True,
        pinned_context={},
    )
    assert decision.action == "clarify"
    assert len(decision.required_inputs_missing) >= 1
    assert 1 <= len(decision.clarifying_questions) <= 3


def test_routing_decision_escalates_owner_specific_when_no_knowledge():
    decision = build_routing_decision(
        query="What is my exact stance on pricing in my own words?",
        mode="QA_FACT",
        intent_label="advice_or_stance",
        interaction_context="owner_chat",
        target_owner_scope=True,
        requires_evidence=True,
        knowledge_available=False,
        pinned_context={},
    )
    assert decision.action == "escalate"
    assert decision.chosen_workflow in {"plan", "answer"}

