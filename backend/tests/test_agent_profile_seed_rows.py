from modules.agent import _build_query_ranked_profile_seed_rows


def test_profile_seed_rows_support_biographical_public_queries():
    rows = _build_query_ranked_profile_seed_rows(
        {
            "name": "Narendra Modi",
            "public_profile": {
                "role": "Prime Minister of India",
                "organization": "Government of India",
                "headline": "Heads the Government of India",
                "bio": (
                    "Born on 17 September 1950 in Vadnagar, Gujarat, Narendra Modi is an Indian politician "
                    "from the Bharatiya Janata Party who has led the country as Prime Minister since 26 May 2014."
                ),
                "contributions": [
                    "Joined Bharatiya Janata Party (BJP)",
                    "Served as Chief Minister of Gujarat",
                ],
                "work_experience": [
                    {
                        "role": "Chief Minister",
                        "company": "Gujarat",
                        "start_year": 2001,
                        "end_year": 2014,
                        "description": "He served as Chief Minister of Gujarat from 2001 to 2014.",
                    }
                ],
                "key_achievements": [
                    "Narendra Modi has been Prime Minister of India since 26 May 2014.",
                ],
            },
        },
        "how you got into politics?",
        limit=4,
    )

    assert rows
    combined = " ".join(str(row.get("text") or "") for row in rows).lower()
    assert "bharatiya janata party" in combined or "chief minister" in combined or "politician" in combined
