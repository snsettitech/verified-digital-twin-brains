import modules.public_profile_pack as profile_pack


def _sample_research_result():
    return {
        "input": {"name": "Narendra Modi", "hints": {"website": "https://www.narendramodi.in/"}},
        "claimed_identity": {"canonical_name": "Narendra Damodardas Modi"},
        "bio": {
            "short": "Narendra Modi is the 14th and current Prime Minister of India, serving since May 2014.",
            "medium": (
                "Narendra Modi is the 14th and current Prime Minister of India. "
                "He previously served as Chief Minister of Gujarat and is known for Digital India and G20 leadership."
            ),
        },
        "profile_summary": {
            "what_they_do": [
                "Leads the Government of India and drives national digital, economic, and infrastructure strategy."
            ],
            "expertise_topics": [
                {"topic": "Public Administration", "confidence": 0.93, "evidence_count": 8},
                {"topic": "Political Strategy", "confidence": 0.88, "evidence_count": 6},
            ],
            "organizations": ["Government of India", "Bharatiya Janata Party"],
            "locations": ["India"],
            "public_roles": ["Prime Minister of India"],
        },
        "claims": [
            {
                "claim_id": "claim_1",
                "text": "Earned a Bachelor of Arts in Political Science from University of Delhi in 1978.",
                "claim_type": "credential",
                "status": "verified",
                "confidence": 0.84,
                "citations": ["src1"],
            },
            {
                "claim_id": "claim_2",
                "text": "Worked as Chief Minister at Government of Gujarat from 2001 to 2014.",
                "claim_type": "experience",
                "status": "verified",
                "confidence": 0.83,
                "citations": ["src1"],
            },
            {
                "claim_id": "claim_3",
                "text": "Served as Prime Minister of India for Government of India from 2014.",
                "claim_type": "role",
                "status": "verified",
                "confidence": 0.91,
                "citations": ["src1"],
            },
            {
                "claim_id": "claim_4",
                "text": "Led the Digital India initiative to expand public digital infrastructure.",
                "claim_type": "project",
                "status": "partially_verified",
                "confidence": 0.78,
                "citations": ["src2"],
            },
        ],
        "timeline": [
            {
                "date_or_range": "2001-2014",
                "event": "Worked as Chief Minister at Government of Gujarat from 2001 to 2014.",
                "confidence": 0.81,
                "citations": ["src1"],
            },
            {
                "date_or_range": "2014-present",
                "event": "Served as Prime Minister of India for Government of India from 2014.",
                "confidence": 0.92,
                "citations": ["src1"],
            },
        ],
        "suggested_followup_questions": [
            "What are the signature policies associated with Narendra Modi?",
            "What leadership style is Narendra Modi known for?",
        ],
        "prepared_question_answers": [
            {
                "question": "What public role is Narendra Modi associated with?",
                "answer": "Prime Minister of India.",
                "confidence": 0.93,
                "citations": ["src1"],
            }
        ],
        "sources": [
            {
                "source_id": "src1",
                "url": "https://www.pmindia.gov.in/en/prime-minister/",
                "title": "Prime Minister of India",
                "source_type": "profile",
                "used_in_final": True,
                "identity_match_confidence": 0.98,
            },
            {
                "source_id": "src2",
                "url": "https://en.wikipedia.org/wiki/Narendra_Modi",
                "title": "Narendra Modi",
                "source_type": "profile",
                "used_in_final": True,
                "identity_match_confidence": 0.91,
            },
        ],
    }


def test_build_research_profile_projection_materializes_demo_style_fields(monkeypatch):
    monkeypatch.setattr(
        profile_pack,
        "_fetch_wikipedia_thumbnail",
        lambda _url: "https://upload.wikimedia.org/wikipedia/commons/modi.jpg",
    )
    monkeypatch.setattr(profile_pack, "_fetch_remote_text", lambda _url, **_kwargs: "")

    projection = profile_pack.build_research_profile_projection(
        {
            "id": "twin-1",
            "name": "Narendra Modi",
            "description": "",
            "settings": {},
        },
        _sample_research_result(),
        source_flow="name_first",
    )

    public_profile = projection["public_profile"]
    identity_pack = projection["persona_identity_pack"]
    public_profile_meta = projection["public_profile_meta"]

    assert public_profile["display_name"] == "Narendra Damodardas Modi"
    assert public_profile["role"] == "Prime Minister of India"
    assert public_profile["organization"] == "Government of India"
    assert "Public Administration" in public_profile["areas_of_expertise"]
    assert public_profile["short_description"].startswith("Narendra Modi is the 14th and current Prime Minister")
    assert public_profile["education"][0]["institution"] == "University of Delhi"
    assert public_profile["work_experience"][0]["company"] == "Government of Gujarat"
    assert public_profile["social_links"]["website"] == "https://www.narendramodi.in/"
    assert public_profile["social_links"]["wikipedia"] == "https://en.wikipedia.org/wiki/Narendra_Modi"
    assert public_profile["image_url"] == "https://upload.wikimedia.org/wikipedia/commons/modi.jpg"
    assert public_profile["pinned_questions"][0].startswith("What are the signature policies")
    assert identity_pack["display_name"] == public_profile["display_name"]
    assert identity_pack["expertise_areas"] == public_profile["areas_of_expertise"]
    assert public_profile_meta["source_flow"] == "name_first"
    assert public_profile_meta["image_status"] == "resolved"
    assert public_profile_meta["image_source_type"] == "wikipedia"
    assert public_profile_meta["completeness_score"] >= 80.0


def test_build_research_profile_projection_preserves_owner_locked_image():
    projection = profile_pack.build_research_profile_projection(
        {
            "id": "twin-1",
            "name": "Narendra Modi",
            "description": "",
            "settings": {
                "public_profile": {
                    "image_url": "https://cdn.example.com/owner-uploaded.jpg",
                    "avatar_url": "https://cdn.example.com/owner-uploaded.jpg",
                },
                "public_profile_meta": {
                    "image_source_type": "owner_uploaded",
                    "image_source_url": "https://cdn.example.com/owner-uploaded.jpg",
                    "image_confidence": 1.0,
                },
            },
        },
        _sample_research_result(),
        source_flow="backfill",
    )

    assert projection["public_profile"]["image_url"] == "https://cdn.example.com/owner-uploaded.jpg"
    assert projection["public_profile_meta"]["image_source_type"] == "owner_uploaded"
    assert projection["public_profile_meta"]["image_status"] == "resolved"


def test_build_public_profile_pack_prefers_seeded_public_profile_fields(monkeypatch):
    monkeypatch.setattr(profile_pack, "_fetch_answerability_score", lambda _twin_id: 72.0)
    monkeypatch.setattr(profile_pack, "_fetch_verified_claim_count", lambda _twin_id: 5)
    monkeypatch.setattr(profile_pack, "_fetch_public_topics", lambda _twin_id: [])
    monkeypatch.setattr(profile_pack, "_fetch_public_claims", lambda _twin_id: [])
    monkeypatch.setattr(profile_pack, "_fetch_timeline_events", lambda _twin_id: [])
    monkeypatch.setattr(profile_pack, "_fetch_style_profile", lambda _twin_id: {})

    twin = {
        "id": "twin-1",
        "name": "Narendra Damodardas Modi",
        "created_at": "2026-03-16T18:31:56",
        "updated_at": "2026-03-16T18:33:16",
        "settings": {
            "public_profile": {
                "display_name": "Narendra Damodardas Modi",
                "occupation": "Prime Minister of India, Politician",
                "headline": "Prime Minister of India",
                "bio": "Narendra Modi is the 14th and current Prime Minister of India.",
                "short_description": "Narendra Modi is the 14th and current Prime Minister of India.",
                "image_url": "https://example.com/modi.jpg",
                "birth_year": 1950,
                "nationality": "Indian",
                "areas_of_expertise": ["Public Administration", "Political Strategy"],
                "education": [
                    {
                        "institution": "University of Delhi",
                        "degree": "Bachelor of Arts",
                        "field": "Political Science",
                        "end_year": 1978,
                    }
                ],
                "work_experience": [
                    {
                        "company": "Government of India",
                        "role": "Prime Minister",
                        "description": "Served as Prime Minister of India from 2014.",
                        "start_year": 2014,
                    }
                ],
            }
        },
    }

    pack = profile_pack.build_public_profile_pack(twin)

    assert pack["occupation"] == "Prime Minister of India, Politician"
    assert pack["birth_year"] == 1950
    assert pack["nationality"] == "Indian"
    assert pack["image_url"] == "https://example.com/modi.jpg"
    assert pack["education"][0]["institution"] == "University of Delhi"
    assert pack["work_experience"][0]["company"] == "Government of India"
    assert pack["answerability_score"] == 72.0
    assert pack["verified_claims_count"] == 5
    assert pack["profile_meta"] == {}


def test_build_existing_profile_projection_materializes_meta_from_seeded_profile():
    projection = profile_pack.build_existing_profile_projection(
        {
            "id": "twin-1",
            "name": "Narendra Damodardas Modi",
            "description": "Prime Minister of India.",
            "settings": {
                "public_profile": {
                    "display_name": "Narendra Damodardas Modi",
                    "headline": "Prime Minister of India",
                    "bio": "Narendra Modi is the 14th and current Prime Minister of India.",
                    "areas_of_expertise": ["Public Administration"],
                    "image_url": "https://example.com/modi.jpg",
                }
            },
        },
        source_flow="link_first",
    )

    assert projection["public_profile"]["display_name"] == "Narendra Damodardas Modi"
    assert projection["public_profile_meta"]["source_flow"] == "link_first"
    assert projection["public_profile_meta"]["image_status"] == "resolved"
    assert projection["public_profile_meta"]["completeness_score"] > 0
