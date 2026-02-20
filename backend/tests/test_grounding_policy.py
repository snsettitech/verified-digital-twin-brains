import pytest

from modules.grounding_policy import get_grounding_policy


@pytest.mark.parametrize(
    "query",
    ["hi", "hello", "thanks", "good morning"],
)
def test_smalltalk_policy(query: str):
    policy = get_grounding_policy(query)
    assert policy["is_smalltalk"] is True
    assert policy["query_class"] == "smalltalk"
    assert policy["requires_evidence"] is False
    assert policy["strict_grounding"] is False


def test_identity_policy():
    policy = get_grounding_policy("Who are you?")
    assert policy["is_smalltalk"] is False
    assert policy["query_class"] == "identity"
    assert policy["requires_evidence"] is True


def test_quote_policy_enables_line_extractor():
    policy = get_grounding_policy("Quote the exact line about your background.")
    assert policy["quote_intent"] is True
    assert policy["allow_line_extractor"] is True


def test_explicit_source_requests_are_strict():
    policy = get_grounding_policy("Based on my sources, what is my stance on GTM?")
    assert policy["strict_grounding"] is True
    assert policy["requires_evidence"] is True
