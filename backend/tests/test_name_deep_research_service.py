import pytest

from modules.name_deep_research_service import NameDeepResearchService


def _minimal_valid_result() -> dict:
    return {
        "run_id": "run-1",
        "input": {
            "name": "Ada Lovelace",
            "hints": {"location": None, "company": None, "website": None},
        },
        "claimed_identity": {
            "canonical_name": "Ada Lovelace",
            "is_match_confidence": 0.9,
            "disambiguation_notes": ["single dominant profile"],
            "possible_duplicates": [],
        },
        "bio": {
            "short": "Ada Lovelace was a mathematician [src-1].",
            "medium": "She collaborated on analytical engine concepts [src-1].",
            "long": "Her work is documented in historical archives [src-1].",
        },
        "profile_summary": {
            "what_they_do": ["Mathematics and early computing [src-1]"],
            "expertise_topics": [{"topic": "computing", "confidence": 0.9, "evidence_count": 1}],
            "organizations": ["Royal Society archives"],
            "locations": ["London"],
            "public_roles": ["Mathematician"],
        },
        "timeline": [
            {
                "date_or_range": "1843",
                "event": "Published analytical engine notes.",
                "confidence": 0.8,
                "citations": ["src-1"],
            }
        ],
        "claims": [
            {
                "claim_id": "claim-1",
                "text": "Published analytical engine notes.",
                "claim_type": "project",
                "status": "verified",
                "confidence": 0.8,
                "citations": ["src-1"],
                "notes": "grounded in source",
            }
        ],
        "known_unknowns": [{"question": "Unknown question", "why_missing": "missing evidence"}],
        "suggested_followup_questions": ["Any primary manuscripts?"],
        "crawl_stats": {
            "queries_used": ["Ada Lovelace biography"],
            "urls_considered": 1,
            "urls_crawled": 1,
            "urls_blocked": 0,
            "sources_used_in_final": 1,
            "words_extracted": 1200,
            "run_started_at": "2026-02-25T00:00:00+00:00",
            "run_completed_at": "2026-02-25T00:05:00+00:00",
        },
        "quality": {
            "overall_confidence": 0.8,
            "freshness_score": 0.4,
            "coverage_score": 0.5,
            "hallucination_risk": "low",
            "warnings": [],
        },
        "sources": [
            {
                "source_id": "src-1",
                "url": "https://example.com/ada",
                "title": "Ada profile",
                "source_type": "profile",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.9,
                "used_in_final": True,
            }
        ],
    }


class TestNameDeepResearchUnits:
    def test_build_queries_name_only_and_hints(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
        queries = service.build_queries(
            name="Satya Nadella",
            hints={"location": "Seattle", "company": "Microsoft", "website": "https://microsoft.com"},
        )
        assert len(queries) > 5
        assert any("Satya Nadella" in q for q in queries)
        assert any("Microsoft" in q for q in queries)
        assert len(queries) == len(set(queries))

    def test_dedupe_urls_canonicalization(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
        urls = [
            "https://example.com/profile?utm_source=test",
            "https://example.com/profile",
            "https://example.com/profile/",
        ]
        deduped = service.dedupe_urls(urls)
        assert len(deduped) == 1

    def test_schema_validation_requires_citations(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
        doc = _minimal_valid_result()
        doc["claims"][0]["citations"] = []
        with pytest.raises(Exception):
            service.validate_result_schema(doc)


class TestNameDeepResearchIntegrationPaths:
    @pytest.mark.asyncio
    async def test_happy_path_synthesis_with_mock_model(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())

        async def fake_invoke(**kwargs):
            result = _minimal_valid_result()
            result["claims"][0]["citations"] = ["src-1"]
            return result

        async def fake_resolve_model():
            return "o3"

        async def fake_candidates():
            return ["o3"]

        service._invoke_reasoning_model = fake_invoke  # type: ignore[assignment]
        service._resolve_reasoning_model = fake_resolve_model  # type: ignore[assignment]
        service._reasoning_model_candidates = fake_candidates  # type: ignore[assignment]

        source_rows = [
            {
                "id": "src-1",
                "canonical_url": "https://example.com/ada",
                "url": "https://example.com/ada",
                "title": "Ada profile",
                "source_type": "profile",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.92,
                "used_in_final": True,
            }
        ]
        ranked = [
            service._rank_evidence(source_rows, [  # pylint: disable=protected-access
                {"source_id": "src-1", "extracted_text": "Ada was a mathematician and writer."}
            ])[0]
        ]

        result, model = await service._synthesize_result(  # pylint: disable=protected-access
            run_id="run-1",
            name="Ada Lovelace",
            hints={"location": None, "company": None, "website": None},
            queries=["Ada Lovelace biography"],
            source_rows=source_rows,
            ranked_evidence=ranked,
            run_started_at="2026-02-25T00:00:00+00:00",
        )
        assert model == "o3"
        assert result["run_id"] == "run-1"
        assert result["claims"][0]["citations"] == ["src-1"]

    def test_ambiguous_name_path_fallback(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
        result = service._build_fallback_result(  # pylint: disable=protected-access
            run_id="run-amb",
            name="John Smith",
            hints={"location": None, "company": None, "website": None},
            queries=["John Smith profile"],
            source_items=[],
            run_started_at="2026-02-25T00:00:00+00:00",
            run_completed_at="2026-02-25T00:02:00+00:00",
            warning="ambiguous identity",
        )
        assert result["claimed_identity"]["canonical_name"] == "John Smith"
        assert result["quality"]["hallucination_risk"] == "high"

    def test_blocked_source_path_fallback_stats(self):
        service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
        result = service._build_fallback_result(  # pylint: disable=protected-access
            run_id="run-blocked",
            name="Example Person",
            hints={"location": None, "company": None, "website": None},
            queries=["Example Person linkedin"],
            source_items=[
                {
                    "source_id": "src-1",
                    "url": "https://linkedin.com/in/example",
                    "title": "",
                    "source_type": "linkedin",
                    "published_at": None,
                    "retrieved_at": "2026-02-25T00:01:00+00:00",
                    "content_quality": "manual_needed",
                    "identity_match_confidence": 0.1,
                    "used_in_final": False,
                }
            ],
            run_started_at="2026-02-25T00:00:00+00:00",
            run_completed_at="2026-02-25T00:02:00+00:00",
            warning="blocked content",
        )
        assert result["crawl_stats"]["urls_blocked"] == 1
        assert "blocked content" in result["quality"]["warnings"][0]
