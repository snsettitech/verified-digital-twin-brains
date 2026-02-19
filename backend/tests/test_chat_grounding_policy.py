import pytest

from routers.chat import _query_requires_strict_grounding
from modules.agent import _is_smalltalk_query


@pytest.mark.parametrize(
    "query",
    [
        "hi",
        "hi!",
        "hello",
        "hey",
        "who are you?",
        "introduce yourself",
        "tell me about yourself",
        "how's your day",
        "yes. i want to ask you about antler",
        "do you know antler",
    ],
)
def test_strict_grounding_is_off_for_conversational_queries(query: str):
    assert _query_requires_strict_grounding(query) is False


@pytest.mark.parametrize(
    "query",
    [
        "What do I think about AI safety?",
        "What's my stance on GTM?",
        "How do I decide on seed investments?",
        "Answer based on my sources.",
        "Cite this from my documents.",
    ],
)
def test_strict_grounding_is_on_for_owner_specific_or_source_queries(query: str):
    assert _query_requires_strict_grounding(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "hi",
        "hello",
        "thanks",
        "ok",
        "cool",
        "how's your day",
    ],
)
def test_smalltalk_detector_covers_greetings_and_acks(query: str):
    assert _is_smalltalk_query(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "who are you?",
        "introduce yourself",
        "tell me about yourself",
        "what do you do",
    ],
)
def test_identity_queries_are_not_smalltalk(query: str):
    assert _is_smalltalk_query(query) is False
