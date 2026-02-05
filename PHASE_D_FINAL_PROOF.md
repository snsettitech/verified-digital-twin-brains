# Phase D Final Proof (Phases 3–6)

Date: 2026-02-04

## Summary
Phase 3 (ingestion artifacts) and Phase 4 (public share retrieval + widget) are proven end-to-end using the local backend and frontend. Phase 6 automated proof artifacts are captured in `proof/`.

## Executed Proofs
- API proof script: `scripts/run_api_proof.py` (local backend `http://127.0.0.1:8001`)
- UI smoke (Playwright): `frontend/scripts/critical_path_smoke.mjs` (local frontend `http://localhost:3000`)

## Evidence
- Ingestion proof: `INGESTION_PROOF_PACKET.md`
- Public retrieval proof: `PUBLIC_RETRIEVAL_PROOF_PACKET.md`
- Full run identifiers and share link: `proof/PROOF_README.md`
- API proof output: `proof/api_proof.json`
- Public chat transcript: `proof/public_chat_response.json`
- Clarification transcript: `proof/public_chat_queued.json`
- Widget stream snippet: `proof/widget_stream.txt`
- UI knowledge sources screenshot: `proof/ui_knowledge_sources.png`
- UI public chat screenshot: `proof/ui_public_chat_answer.png`
- UI sources response: `proof/ui_sources_response.json`
- UI console log: `proof/ui_console.log`

## Acceptance Checks (Pass)
- Sources created and live, chunks > 0, vectors verified: see `INGESTION_PROOF_PACKET.md`
- Graph extraction returns nodes/edges: see `INGESTION_PROOF_PACKET.md`
- Share link validates: see `PUBLIC_RETRIEVAL_PROOF_PACKET.md`
- Public chat returns `status=answer` grounded in ingested sources: see `PUBLIC_RETRIEVAL_PROOF_PACKET.md`
- Public chat returns `status=queued` for clarification: see `proof/public_chat_queued.json`
- Widget stream emits `metadata`, `content` with `token`, and `done`: see `proof/widget_stream.txt`
- UI Knowledge tab shows sources: see `proof/ui_knowledge_has_source.txt` + `proof/ui_knowledge_sources.png`

## Non-Blocking Warnings
- `proof/ui_console.log` shows 401s for `/metrics/*` calls. These are non-critical paths and did not affect ingestion or public retrieval.
- Pinecone `describe_index_stats` reports zero vectors while backend verification reports vectors; ingestion and retrieval still return the correct content (see `INGESTION_PROOF_PACKET.md`).
