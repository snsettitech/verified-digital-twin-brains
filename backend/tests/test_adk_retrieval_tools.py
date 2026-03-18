import json

from adk_core.tools.retrieval_tools import _merge_citations, _quote_score


def test_merge_citations_preserves_order_and_dedupes():
    merged = _merge_citations(["a", "b"], ["b", "c"], [])
    assert merged == ["a", "b", "c"]


def test_quote_score_prefers_overlap():
    high = _quote_score("shipping products", {"quote_text": "I like shipping great products fast"})
    low = _quote_score("shipping products", {"quote_text": "Markets matter when teams learn"})
    assert high > low
