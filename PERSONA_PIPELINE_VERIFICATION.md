# Persona Pipeline Verification

## 1) Feature Flags

All new behavior is default-off.

```bash
# Phase 1: extraction only
PERSONA_EXTRACTION_ENABLED=true
PERSONA_FASTPATH_ENABLED=false
PERSONA_DRAFT_PROFILE_ALLOWED=false

# Phase 2: extraction + fast-path (approved profiles only)
PERSONA_EXTRACTION_ENABLED=true
PERSONA_FASTPATH_ENABLED=true
PERSONA_DRAFT_PROFILE_ALLOWED=false

# Optional testing mode: allow draft profiles in fast-path
PERSONA_DRAFT_PROFILE_ALLOWED=true
```

## 2) Seed a Sample Persona Profile

Canonical profile is stored in `twins.settings.persona_identity_pack`.
Set `profile_status` to `approved` for production fast-path usage.

Example SQL:

```sql
update twins
set settings = jsonb_set(
  coalesce(settings, '{}'::jsonb),
  '{persona_identity_pack}',
  '{
    "twin_id": "REPLACE_TWIN_ID",
    "display_name": "Alex Rivera",
    "one_line_intro": "I help founders build AI products with practical execution.",
    "short_intro": "I am a digital representation built from Alex Rivera''s public sources.",
    "disclosure_line": "I’m a digital AI representation, not Alex directly.",
    "contact_handoff_line": "For direct contact, please use official public channels.",
    "preferred_contact_channel": "linkedin",
    "social_links": {"linkedin": "https://linkedin.com/in/alex"},
    "expertise_areas": ["ai systems", "go-to-market"],
    "tone_tags": ["direct", "approachable"],
    "profile_status": "approved"
  }'::jsonb,
  true
)
where id = 'REPLACE_TWIN_ID';
```

## 3) Example Chat Prompts and Expected Behavior

- `Who are you?`
  - With fast-path enabled + approved profile: answer comes from canonical profile, no retrieval required.
  - With flags off: current RAG route remains unchanged.

- `Are you really Alex Rivera?`
  - With fast-path enabled + approved profile: response includes disclosure line.

- `Can I talk to Alex directly?`
  - With fast-path enabled + approved profile: response includes contact handoff + disclosure line.

- `What can you help with?`
  - With fast-path enabled + approved profile: response uses `expertise_areas`.

## 4) Extraction Verification

With `PERSONA_EXTRACTION_ENABLED=true`, ingest any source and verify:

- `twins.settings.persona_extraction_candidates` is populated.
- `twins.settings.persona_identity_pack` receives high-confidence draft fields.
- low-confidence facts enqueue an `owner_review_queue` item with reason `persona_extraction_low_confidence`.

## 5) Rollback

Immediate rollback requires flags only:

```bash
PERSONA_EXTRACTION_ENABLED=false
PERSONA_FASTPATH_ENABLED=false
PERSONA_DRAFT_PROFILE_ALLOWED=false
```

No schema rollback is needed.
