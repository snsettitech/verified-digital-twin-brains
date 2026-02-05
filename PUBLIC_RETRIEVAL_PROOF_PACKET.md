# Public Retrieval Proof Packet

Date: 2026-02-04
Status: Completed (local backend run)

This packet documents share-link validation and public retrieval via share chat and widget.

**Share Link Generation**

- Twin ID: `003eb646-362e-4dad-a116-f478ea620b19`
- `POST /twins/{twin_id}/share-link` response:
- share_token: `a2909e...5c9ad3` (redacted)
- share_url: `http://localhost:3000/share/003eb646-362e-4dad-a116-f478ea620b19/a2909ea0-7518-460f-88c1-b7df395c9ad3`
- public_share_enabled: `true`

**Share Link Validation**

- `GET /public/validate-share/{twin_id}/{token}` response:
- valid: `true`
- twin_name: `Critical Path Proof Twin 1770201157`

**Public Share Chat**

- Request: `POST /public/chat/{twin_id}/{token}`
- Expected: `{ status: "answer" }` with content grounded in ingested sources.
- Example response:
- status: `answer`
- response snippet: `The unique phrase in the critical path proof file is **CRITICAL_PATH_PROOF_1770201158**.`
- citations: `graph-e65a5e2c, 1ce88e61-6087-4e3a-8c11-a1c2fad5aa53, ab57d0b0-6595-4e8f-86fb-181600ee04d5, graph-b867d453`
- used_owner_memory: `false`

**Clarification Path**

- Request: `POST /public/chat/{twin_id}/{token}` with a stance question
- Response:
- status: `queued`
- clarification_id: `7cdf1e87-7677-4eb5-a256-8b1d090d1e02`
- question: `What lens should guide decisions about stance orion-policy-1770201193 escalation framework incidents? Choose one (or answer in one sentence).`
- options: `Pragmatic ROI lens | Ethics/values-first lens | Long-term risk lens`

**Widget Chat**

- Widget request: `POST /chat-widget/{twin_id}` with API key.
- Streamed events:
- `metadata` event includes `session_id`.
- `content` events include `token` (fallback to `content`).
- `done` event emitted.

**Evidence**

- Share URL opened in browser: `http://localhost:3000/share/003eb646-362e-4dad-a116-f478ea620b19/a2909ea0-7518-460f-88c1-b7df395c9ad3`
- Public chat transcript snippet: `proof/public_chat_response.json`
- Clarification transcript: `proof/public_chat_queued.json`
- Widget transcript snippet: `proof/widget_stream.txt`
- Share validation response: `proof/public_validate_share.json`

**Errors/Anomalies**

- `None` (run completed successfully)
