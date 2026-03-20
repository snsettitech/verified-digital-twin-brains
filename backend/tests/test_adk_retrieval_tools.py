import json
from types import SimpleNamespace

import pytest

from adk_core.tools import retrieval_tools
from adk_core.tools.retrieval_tools import _merge_citations, _quote_score


def test_merge_citations_preserves_order_and_dedupes():
    merged = _merge_citations(["a", "b"], ["b", "c"], [])
    assert merged == ["a", "b", "c"]


def test_quote_score_prefers_overlap():
    high = _quote_score("shipping products", {"quote_text": "I like shipping great products fast"})
    low = _quote_score("shipping products", {"quote_text": "Markets matter when teams learn"})
    assert high > low


@pytest.mark.asyncio
async def test_retrieve_fact_context_uses_persona_artifact_without_legacy_retrieval(monkeypatch):
    artifact = {
        "subject_name": "Ada Lovelace",
        "claims": [
            {
                "text": "She ships analytical products with first-principles rigor.",
                "confidence": 0.9,
                "source_ids": ["src-claim"],
            }
        ],
        "timeline": [
            {
                "date_or_range": "1843",
                "event": "Published analytical engine notes for technical audiences.",
                "confidence": 0.8,
                "source_ids": ["src-timeline"],
            }
        ],
        "retrieval_seeds": ["first principles", "shipping products"],
        "public_profile": {"headline": "Analytical engine pioneer"},
    }
    monkeypatch.setattr(
        retrieval_tools,
        "_persona_repository",
        SimpleNamespace(
            get_active_artifact=lambda twin_id, tenant_id: {"artifact_json": artifact},
            list_quotes=lambda twin_id, tenant_id: [],
        ),
    )
    monkeypatch.setattr(
        retrieval_tools,
        "_conversation_repository",
        SimpleNamespace(
            list_messages=lambda conversation_id: [
                {"role": "user", "content": "How do you ship products?"}
            ]
        ),
    )
    monkeypatch.setattr(
        retrieval_tools,
        "_query_integrated_persona_namespace",
        lambda query, twin_id: [],
    )
    ctx = SimpleNamespace(
        state={
            "twin_id": "twin-1",
            "tenant_id": "tenant-1",
            "conversation_id": "conv-1",
        }
    )

    result = await retrieval_tools.retrieve_fact_context("How do you ship products?", ctx)

    contexts = json.loads(ctx.state["fact_context_json"])
    assert result["status"] == "success"
    assert result["result_count"] >= 1
    assert any(item["category"] == "persona_claim" for item in contexts)
    assert "src-claim" in result["citations"]


@pytest.mark.asyncio
async def test_retrieve_fact_context_merges_integrated_namespace_hits(monkeypatch):
    artifact = {
        "subject_name": "Ada Lovelace",
        "claims": [],
        "timeline": [],
        "retrieval_seeds": [],
    }
    monkeypatch.setattr(
        retrieval_tools,
        "_persona_repository",
        SimpleNamespace(
            get_active_artifact=lambda twin_id, tenant_id: {"artifact_json": artifact},
            list_quotes=lambda twin_id, tenant_id: [],
        ),
    )
    monkeypatch.setattr(
        retrieval_tools,
        "_conversation_repository",
        SimpleNamespace(list_messages=lambda conversation_id: []),
    )
    monkeypatch.setattr(
        retrieval_tools,
        "_query_integrated_persona_namespace",
        lambda query, twin_id: [
            {
                "source_id": "src-namespace",
                "text": "She writes about analytical engines and symbolic systems.",
                "score": 2.5,
                "category": "claim",
            }
        ],
    )
    ctx = SimpleNamespace(state={"twin_id": "twin-1", "tenant_id": "tenant-1"})

    result = await retrieval_tools.retrieve_fact_context("analytical engines", ctx)

    contexts = json.loads(ctx.state["fact_context_json"])
    assert result["status"] == "success"
    assert result["citations"] == ["src-namespace"]
    assert contexts[0]["source_id"] == "src-namespace"


def test_retrieve_quote_context_falls_back_to_artifact_quote_pack(monkeypatch):
    artifact = {
        "quote_pack": [
            {
                "quote": "I prefer first-principles reasoning when building products.",
                "source_id": "src-quote",
                "context": "Interview",
                "confidence": 0.88,
            }
        ]
    }
    monkeypatch.setattr(
        retrieval_tools,
        "_persona_repository",
        SimpleNamespace(
            get_active_artifact=lambda twin_id, tenant_id: {"artifact_json": artifact},
            list_quotes=lambda twin_id, tenant_id: [],
        ),
    )
    ctx = SimpleNamespace(state={"twin_id": "twin-1", "tenant_id": "tenant-1"})

    result = retrieval_tools.retrieve_quote_context("first principles", ctx)

    quotes = json.loads(ctx.state["quote_context_json"])
    assert result["status"] == "success"
    assert result["citations"] == ["src-quote"]
    assert quotes[0]["quote"].startswith("I prefer first-principles")
