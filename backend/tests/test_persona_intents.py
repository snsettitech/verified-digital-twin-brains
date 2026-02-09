from modules.persona_intents import (
    classify_query_intent,
    intent_from_dialogue_mode,
    normalize_intent_label,
)


def test_intent_from_dialogue_mode_mapping():
    assert intent_from_dialogue_mode("SMALLTALK") == "meta_or_system"
    assert intent_from_dialogue_mode("QA_FACT") == "factual_with_evidence"
    assert intent_from_dialogue_mode("unknown") is None


def test_classify_query_intent_keyword_fallbacks():
    assert classify_query_intent("Can you summarize this transcript?") == "summarize_or_transform"
    assert classify_query_intent("What do you recommend I do next?") == "advice_or_stance"
    assert classify_query_intent("Please schedule a call for tomorrow") == "action_or_tool_execution"
    assert classify_query_intent("who are you and what are your rules?") == "meta_or_system"


def test_normalize_intent_label_defaults_for_unknown():
    assert normalize_intent_label("factual_with_evidence") == "factual_with_evidence"
    assert normalize_intent_label("bad_label") == "factual_with_evidence"

