from modules.persona_extraction_service import extract_persona_facts


def test_persona_extraction_schema_contains_confidence_and_evidence():
    text = (
        "My name is Sainath Setti. I am the founder of Digital Minds.\n\n"
        "I help teams with AI systems and cloud architecture. "
        "You can connect on LinkedIn: https://linkedin.com/in/sainathsetti "
        "or email me at hello@example.com."
    )
    payload = extract_persona_facts(
        source_id="source-1",
        text=text,
        source_metadata={"provider": "url", "filename": "about-me.md"},
    )

    assert payload["schema_version"] == "persona_extraction.v1"
    assert payload["source_id"] == "source-1"
    assert isinstance(payload.get("facts"), dict)

    required_fields = [
        "full_name",
        "brand_name",
        "roles_titles",
        "credentials",
        "company_organization",
        "expertise_areas",
        "one_line_intro",
        "short_intro",
        "public_contact_links",
        "preferred_contact_channel",
        "tone_tags",
        "disclosure_line",
        "contact_handoff_line",
    ]
    for key in required_fields:
        assert key in payload["facts"]
        assert isinstance(payload["facts"][key], list)

    assert payload["facts"]["full_name"], "expected at least one full_name candidate"
    first = payload["facts"]["full_name"][0]
    assert "value" in first
    assert "confidence" in first
    assert "evidence" in first
    assert "source_provenance" in first
    assert isinstance(first["evidence"], list)
    assert first["evidence"][0]["source_id"] == "source-1"
