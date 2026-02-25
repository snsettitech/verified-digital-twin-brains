import pytest

from modules.name_deep_research_service import NameDeepResearchService, RankedEvidence
from modules.name_deep_research_synthesis import normalize_name_deep_research_synthesis_payload


def _minimal_valid_result(run_id: str = "run-1") -> dict:
    return {
        "run_id": run_id,
        "input": {
            "name": "Chris Carder",
            "hints": {"location": None, "company": "Schulich School of Business", "website": None},
        },
        "claimed_identity": {
            "canonical_name": "Chris Carder",
            "is_match_confidence": 0.72,
            "disambiguation_notes": ["Multiple public profiles detected."],
            "possible_duplicates": [],
        },
        "bio": {
            "short": "Chris Carder is associated with Schulich [src-1].",
            "medium": "Chris Carder supports entrepreneurship programming [src-1].",
            "long": "Evidence indicates a Schulich-related profile with caveats [src-1].",
        },
        "profile_summary": {
            "what_they_do": ["Leads entrepreneurship-related initiatives [src-1]"],
            "expertise_topics": [{"topic": "entrepreneurship", "confidence": 0.72, "evidence_count": 1}],
            "organizations": ["Schulich School of Business"],
            "locations": ["Toronto"],
            "public_roles": ["Executive Director"],
        },
        "timeline": [
            {
                "date_or_range": "2024",
                "event": "Publicly listed in a Schulich profile context.",
                "confidence": 0.65,
                "citations": ["src-1"],
            }
        ],
        "claims": [
            {
                "claim_id": "claim_1",
                "text": "Associated with Schulich entrepreneurship ecosystem.",
                "claim_type": "role",
                "status": "partially_verified",
                "confidence": 0.65,
                "citations": ["src-1"],
                "notes": "",
            }
        ],
        "known_unknowns": [
            {"question": "Is this profile uniquely identified?", "why_missing": "Other same-name profiles exist."}
        ],
        "suggested_followup_questions": ["Can this be confirmed through an official organization page?"],
        "crawl_stats": {
            "queries_used": ["Chris Carder Schulich School of Business leadership"],
            "urls_considered": 10,
            "urls_crawled": 3,
            "urls_blocked": 1,
            "sources_used_in_final": 1,
            "words_extracted": 1200,
            "run_started_at": "2026-02-25T00:00:00+00:00",
            "run_completed_at": "2026-02-25T00:04:00+00:00",
        },
        "quality": {
            "overall_confidence": 0.65,
            "freshness_score": 0.6,
            "coverage_score": 0.5,
            "hallucination_risk": "medium",
            "warnings": [],
        },
        "sources": [
            {
                "source_id": "src-1",
                "url": "https://schulich.yorku.ca/faculty/chris-carder",
                "title": "Chris Carder - Schulich School of Business",
                "source_type": "website",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.72,
                "used_in_final": True,
            }
        ],
    }


def _source_rows_for_gating():
    return [
        {
            "id": "src-1",
            "canonical_url": "https://schulich.yorku.ca/faculty/chris-carder",
            "url": "https://schulich.yorku.ca/faculty/chris-carder",
            "title": "Chris Carder - Schulich School of Business",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:00:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.72,
            "used_in_final": False,
            "metadata": {},
        },
        {
            "id": "src-2",
            "canonical_url": "https://www.chriscarderphotography.com/new-works",
            "url": "https://www.chriscarderphotography.com/new-works",
            "title": "chris carder photography",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:00:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.56,
            "used_in_final": False,
            "metadata": {},
        },
        {
            "id": "src-3",
            "canonical_url": "https://kidder.com/professionals/carder-dave",
            "url": "https://kidder.com/professionals/carder-dave",
            "title": "Dave Carder | Office Broker",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:00:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.44,
            "used_in_final": False,
            "metadata": {},
        },
    ]


def _ranked_for_gating():
    return [
        RankedEvidence(
            source_id="src-1",
            rank_score=0.62,
            url="https://schulich.yorku.ca/faculty/chris-carder",
            title="Chris Carder - Schulich School of Business",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:00:00+00:00",
            content_quality="full",
            identity_match_confidence=0.72,
            excerpt="Schulich School of Business and York University profile.",
        ),
        RankedEvidence(
            source_id="src-2",
            rank_score=0.66,
            url="https://www.chriscarderphotography.com/new-works",
            title="chris carder photography",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:00:00+00:00",
            content_quality="full",
            identity_match_confidence=0.56,
            excerpt="Photography portfolio and album pages.",
        ),
        RankedEvidence(
            source_id="src-3",
            rank_score=0.58,
            url="https://kidder.com/professionals/carder-dave",
            title="Dave Carder | Office Broker",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:00:00+00:00",
            content_quality="full",
            identity_match_confidence=0.44,
            excerpt="Real estate office broker biography.",
        ),
    ]


def test_normalization_bio_dict_to_string():
    raw = {
        "bio": {
            "short": {"text": "Short bio"},
            "medium": {"text": "Medium bio"},
            "long": {"text": "Long bio"},
        }
    }
    out = normalize_name_deep_research_synthesis_payload(raw)
    assert out["bio"]["short"] == "Short bio"
    assert out["bio"]["medium"] == "Medium bio"
    assert out["bio"]["long"] == "Long bio"


def test_normalization_timeline_date_text_source_id_mapping():
    raw = {
        "timeline": [{"date": "2024", "text": "Joined org", "source_id": "src-1", "junk": "x"}],
    }
    out = normalize_name_deep_research_synthesis_payload(raw)
    assert out["timeline"][0] == {
        "date_or_range": "2024",
        "event": "Joined org",
        "confidence": 0.5,
        "citations": ["src-1"],
    }


def test_normalization_claims_source_id_to_citations():
    raw = {
        "claims": [
            {
                "claim_id": "c1",
                "text": "Worked at X",
                "claim_type": "role",
                "status": "verified",
                "confidence": 0.7,
                "source_id": "src-1",
                "notes": "",
            }
        ]
    }
    out = normalize_name_deep_research_synthesis_payload(raw)
    assert out["claims"][0]["citations"] == ["src-1"]
    assert out["claims"][0]["claim_type"] == "role"


def test_normalization_scalar_and_dict_to_list_fields():
    raw = {
        "claimed_identity": {"disambiguation_notes": {"text": "Needs review"}},
        "profile_summary": {
            "what_they_do": {"text": "Leads startup programs"},
            "organizations": "Schulich School of Business",
            "locations": "Toronto",
            "public_roles": {"text": "Executive Director"},
            "expertise_topics": {"text": "entrepreneurship, innovation"},
        },
    }
    out = normalize_name_deep_research_synthesis_payload(raw)
    assert out["claimed_identity"]["disambiguation_notes"] == ["Needs review"]
    assert out["profile_summary"]["what_they_do"] == ["Leads startup programs"]
    assert out["profile_summary"]["organizations"] == ["Schulich School of Business"]
    assert out["profile_summary"]["locations"] == ["Toronto"]
    assert out["profile_summary"]["public_roles"] == ["Executive Director"]
    assert len(out["profile_summary"]["expertise_topics"]) == 2


def test_normalization_drops_invalid_extra_fields_without_crashing():
    raw = {
        "quality": {
            "overall_confidence": "evidence_based_with_minor_gaps",
            "freshness_score": 0.4,
            "coverage_score": 0.2,
            "hallucination_risk": "high",
            "warnings": "warn",
            "extra_field": "drop-me",
        },
        "crawl_stats": {"total_sources": 99, "used_sources": 50},
    }
    out = normalize_name_deep_research_synthesis_payload(raw)
    assert out["quality"]["overall_confidence"] == pytest.approx(0.62, rel=1e-3)
    assert "extra_field" not in out["quality"]
    assert "crawl_stats" not in out


def test_stage_a_document_derives_quality_when_model_omits_quality_scores():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    stage_doc = service._build_stage_a_document(  # pylint: disable=protected-access
        run_id="run-quality",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        queries=["Chris Carder Schulich School of Business leadership"],
        source_items=[
            {
                "source_id": "src-1",
                "url": "https://schulich.yorku.ca/faculty/chris-carder",
                "title": "Chris Carder - Schulich School of Business",
                "source_type": "website",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.72,
                "used_in_final": True,
            }
        ],
        normalized_payload={
            "claimed_identity": {
                "canonical_name": "Chris Carder",
                "is_match_confidence": 0.72,
                "disambiguation_notes": ["Needs disambiguation review."],
                "possible_duplicates": [],
            },
            "profile_summary": {
                "what_they_do": ["Leads innovation programs"],
                "expertise_topics": [{"topic": "entrepreneurship", "confidence": 0.7, "evidence_count": 1}],
                "organizations": ["Schulich School of Business"],
                "locations": ["Toronto"],
                "public_roles": ["Executive Director"],
            },
            "timeline": [
                {
                    "date_or_range": "2024",
                    "event": "Profile published.",
                    "confidence": 0.7,
                    "citations": ["src-1"],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim_1",
                    "text": "Associated with Schulich.",
                    "claim_type": "role",
                    "status": "partially_verified",
                    "confidence": 0.7,
                    "citations": ["src-1"],
                    "notes": "",
                }
            ],
            "known_unknowns": [],
            "suggested_followup_questions": ["Any official role start date?"],
            "quality": {"hallucination_risk": "medium", "warnings": []},
        },
        urls_considered=10,
        words_extracted=1200,
        run_started_at="2026-02-25T00:00:00+00:00",
        run_completed_at="2026-02-25T00:04:00+00:00",
    )
    assert stage_doc["quality"]["overall_confidence"] > 0.0
    assert stage_doc["quality"]["freshness_score"] > 0.0
    assert stage_doc["quality"]["coverage_score"] > 0.0


@pytest.mark.asyncio
async def test_two_stage_synthesis_preserves_structured_when_bio_stage_fails():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    service.synthesis_hardening_enabled = True
    service.synthesis_repair_retry_enabled = True

    async def fake_stage_a(**kwargs):
        return _minimal_valid_result(run_id="run-two-stage")

    async def fake_stage_b(**kwargs):
        raise RuntimeError("bio generation failed")

    async def fake_resolve():
        return "o3"

    async def fake_candidates():
        return ["o3"]

    service._run_stage_a_synthesis = fake_stage_a  # type: ignore[assignment]
    service._run_stage_b_bio_generation = fake_stage_b  # type: ignore[assignment]
    service._resolve_reasoning_model = fake_resolve  # type: ignore[assignment]
    service._reasoning_model_candidates = fake_candidates  # type: ignore[assignment]

    source_rows = [
        {
            "id": "src-1",
            "canonical_url": "https://schulich.yorku.ca/faculty/chris-carder",
            "url": "https://schulich.yorku.ca/faculty/chris-carder",
            "title": "Chris Carder - Schulich School of Business",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:01:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.72,
            "used_in_final": True,
        }
    ]
    ranked = [
        RankedEvidence(
            source_id="src-1",
            rank_score=0.62,
            url="https://schulich.yorku.ca/faculty/chris-carder",
            title="Chris Carder - Schulich School of Business",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:01:00+00:00",
            content_quality="full",
            identity_match_confidence=0.72,
            excerpt="Schulich profile",
        )
    ]
    result, model = await service._synthesize_result(  # pylint: disable=protected-access
        run_id="run-two-stage",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        queries=["Chris Carder Schulich School of Business leadership"],
        source_rows=source_rows,
        ranked_evidence=ranked,
        run_started_at="2026-02-25T00:00:00+00:00",
    )
    assert model == "o3"
    assert result["claims"][0]["text"] == "Associated with Schulich entrepreneurship ecosystem."
    assert result["bio"]["short"] == "Unknown. Needs additional evidence."
    assert any("Bio generation fallback applied" in warning for warning in result["quality"]["warnings"])


@pytest.mark.asyncio
async def test_repair_retry_prompt_path_on_validation_failure():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    service.synthesis_hardening_enabled = True
    service.synthesis_repair_retry_enabled = True

    calls = []

    async def fake_stage_a(**kwargs):
        calls.append(kwargs.get("validation_error"))
        if kwargs.get("validation_error") is None:
            raise ValueError("timeline.0.date_or_range missing")
        return _minimal_valid_result(run_id="run-repair")

    async def fake_stage_b(**kwargs):
        return {
            "short": "Short grounded bio [src-1].",
            "medium": "Medium grounded bio [src-1].",
            "long": "Long grounded bio [src-1].",
        }

    async def fake_resolve():
        return "o3"

    async def fake_candidates():
        return ["o3"]

    service._run_stage_a_synthesis = fake_stage_a  # type: ignore[assignment]
    service._run_stage_b_bio_generation = fake_stage_b  # type: ignore[assignment]
    service._resolve_reasoning_model = fake_resolve  # type: ignore[assignment]
    service._reasoning_model_candidates = fake_candidates  # type: ignore[assignment]

    source_rows = [
        {
            "id": "src-1",
            "canonical_url": "https://schulich.yorku.ca/faculty/chris-carder",
            "url": "https://schulich.yorku.ca/faculty/chris-carder",
            "title": "Chris Carder - Schulich School of Business",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:01:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.72,
            "used_in_final": True,
        }
    ]
    ranked = [
        RankedEvidence(
            source_id="src-1",
            rank_score=0.62,
            url="https://schulich.yorku.ca/faculty/chris-carder",
            title="Chris Carder - Schulich School of Business",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:01:00+00:00",
            content_quality="full",
            identity_match_confidence=0.72,
            excerpt="Schulich profile",
        )
    ]
    result, _ = await service._synthesize_result(  # pylint: disable=protected-access
        run_id="run-repair",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        queries=["Chris Carder Schulich School of Business leadership"],
        source_rows=source_rows,
        ranked_evidence=ranked,
        run_started_at="2026-02-25T00:00:00+00:00",
    )
    assert len(calls) == 2
    assert calls[0] is None
    assert isinstance(calls[1], str) and "Validation issues" in calls[1]
    assert result["run_id"] == "run-repair"


def test_identity_gating_excludes_unrelated_sources_with_company_hint():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    service.identity_gating_enabled = True
    selected, decisions = service._select_synthesis_candidates(  # pylint: disable=protected-access
        run_id="run-gating",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        ranked_evidence=_ranked_for_gating(),
        source_rows=_source_rows_for_gating(),
    )
    selected_ids = [item.source_id for item in selected]
    assert "src-1" in selected_ids
    assert "src-2" not in selected_ids
    assert "src-3" not in selected_ids
    assert "TOPIC_MISMATCH_PENALTY" in decisions["src-2"].reason_codes
    assert "EXCLUDED_DIFFERENT_PERSON" in decisions["src-3"].reason_codes


def test_identity_gating_prefers_schulich_york_when_hint_present():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    service.identity_gating_enabled = True

    source_rows = [
        {
            "id": "src-a",
            "canonical_url": "https://schulich.yorku.ca/faculty/chris-carder",
            "url": "https://schulich.yorku.ca/faculty/chris-carder",
            "title": "Chris Carder - Schulich School of Business",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:00:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.68,
            "used_in_final": False,
            "metadata": {},
        },
        {
            "id": "src-b",
            "canonical_url": "https://example.com/chris-carder",
            "url": "https://example.com/chris-carder",
            "title": "Chris Carder profile",
            "source_type": "website",
            "published_at": None,
            "retrieved_at": "2026-02-25T00:00:00+00:00",
            "content_quality": "full",
            "identity_match_confidence": 0.69,
            "used_in_final": False,
            "metadata": {},
        },
    ]
    ranked = [
        RankedEvidence(
            source_id="src-a",
            rank_score=0.52,
            url="https://schulich.yorku.ca/faculty/chris-carder",
            title="Chris Carder - Schulich School of Business",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:00:00+00:00",
            content_quality="full",
            identity_match_confidence=0.68,
            excerpt="York University faculty profile.",
        ),
        RankedEvidence(
            source_id="src-b",
            rank_score=0.60,
            url="https://example.com/chris-carder",
            title="Chris Carder profile",
            source_type="website",
            published_at=None,
            retrieved_at="2026-02-25T00:00:00+00:00",
            content_quality="full",
            identity_match_confidence=0.69,
            excerpt="Generic personal profile with no organization context.",
        ),
    ]
    selected, decisions = service._select_synthesis_candidates(  # pylint: disable=protected-access
        run_id="run-pref",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        ranked_evidence=ranked,
        source_rows=source_rows,
    )
    assert selected[0].source_id == "src-a"
    assert "HINT_MATCH" in decisions["src-a"].reason_codes


def test_stage_a_adds_training_metrics_and_prepared_qa():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    doc = service._build_stage_a_document(  # pylint: disable=protected-access
        run_id="run-metrics",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        queries=["Chris Carder Schulich School of Business leadership"],
        source_items=[
            {
                "source_id": "src-1",
                "url": "https://schulich.yorku.ca/faculty/chris-carder",
                "title": "Chris Carder - Schulich School of Business",
                "source_type": "website",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.74,
                "used_in_final": True,
            }
        ],
        normalized_payload={
            "claimed_identity": {
                "canonical_name": "Chris Carder",
                "is_match_confidence": 0.74,
                "disambiguation_notes": ["single best match"],
                "possible_duplicates": [],
            },
            "profile_summary": {
                "what_they_do": ["Leads startup programs"],
                "expertise_topics": [{"topic": "entrepreneurship", "confidence": 0.7, "evidence_count": 1}],
                "organizations": ["Schulich School of Business"],
                "locations": ["Toronto"],
                "public_roles": ["Executive Director"],
            },
            "timeline": [
                {
                    "date_or_range": "2024",
                    "event": "Public role listed at Schulich.",
                    "confidence": 0.7,
                    "citations": ["src-1"],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim_1",
                    "text": "Associated with Schulich startup ecosystem.",
                    "claim_type": "role",
                    "status": "partially_verified",
                    "confidence": 0.72,
                    "citations": ["src-1"],
                    "notes": "",
                }
            ],
            "known_unknowns": [],
            "suggested_followup_questions": ["What is the official role title?"],
            "quality": {"hallucination_risk": "medium", "warnings": []},
        },
        urls_considered=12,
        words_extracted=4200,
        run_started_at="2026-02-25T00:00:00+00:00",
        run_completed_at="2026-02-25T00:04:00+00:00",
    )
    assert "training_metrics" in doc
    assert doc["training_metrics"]["words_processed"] == 4200
    assert doc["training_metrics"]["mind_score"] >= 0
    assert "prepared_question_answers" in doc
    assert len(doc["prepared_question_answers"]) >= 1
    assert doc["prepared_question_answers"][0]["citations"] == ["src-1"]


def test_fallback_adds_prepared_qa_and_metrics_with_citations():
    service = NameDeepResearchService(db_client=object(), firecrawl_client=object())
    fallback = service._build_fallback_result(  # pylint: disable=protected-access
        run_id="run-fallback-qa",
        name="Chris Carder",
        hints={"location": None, "company": "Schulich School of Business", "website": None},
        queries=["Chris Carder Schulich School of Business"],
        source_items=[
            {
                "source_id": "src-1",
                "url": "https://schulich.yorku.ca/faculty/chris-carder",
                "title": "Chris Carder - Schulich School of Business",
                "source_type": "website",
                "published_at": None,
                "retrieved_at": "2026-02-25T00:01:00+00:00",
                "content_quality": "full",
                "identity_match_confidence": 0.61,
                "used_in_final": True,
            }
        ],
        urls_considered=5,
        words_extracted=1500,
        run_started_at="2026-02-25T00:00:00+00:00",
        run_completed_at="2026-02-25T00:02:00+00:00",
        warning="fallback path",
    )
    assert "training_metrics" in fallback
    assert fallback["training_metrics"]["questions_answerable_est"] >= 0
    assert "prepared_question_answers" in fallback
    assert fallback["prepared_question_answers"]
    assert fallback["prepared_question_answers"][0]["citations"]
