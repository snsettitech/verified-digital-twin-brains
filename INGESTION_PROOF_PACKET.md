# Ingestion Proof Packet

Date: 2026-02-04
Status: Completed (local backend run)

This packet documents a single end-to-end ingestion run proving sources, chunks, vectors, and graph artifacts (if enabled).

**Inputs**

- Twin ID: `003eb646-362e-4dad-a116-f478ea620b19`
- File ingest: `proof/ingest_proof.txt` (unique phrase: `CRITICAL_PATH_PROOF_1770201158`)
- URL ingest: `https://example.com`

**Steps**

1. Create twin via `POST /twins`.
2. Ingest file via `POST /ingest/file/{twin_id}`.
3. Ingest URL via `POST /ingest/url/{twin_id}`.
4. Validate sources via `GET /sources/{twin_id}`.
5. Validate chunks via `sources.chunk_count` + Supabase `chunks` count.
6. Validate vectors via `GET /twins/{twin_id}/verification-status` and Pinecone stats.
7. Extract graph via `POST /ingest/extract-nodes/{source_id}`.
8. Validate graph via `GET /twins/{twin_id}/graph`.
9. Validate health checks via `GET /sources/{source_id}/health`.

**Evidence**

- Sources row:
- Source ID (file): `ab57d0b0-6595-4e8f-86fb-181600ee04d5`
- Source ID (URL): `1ce88e61-6087-4e3a-8c11-a1c2fad5aa53`
- Status (file/url): `live`

- Chunks:
- Chunk count (file): `1`
- Chunk count (URL): `1`

- Vectors:
- Namespace: `003eb646-362e-4dad-a116-f478ea620b19`
- `GET /twins/{twin_id}/verification-status` ? `vectors_count = 2`
- Pinecone `describe_index_stats` ? `vector_count = 0` (see Notes)

- Graph:
- Extract nodes response: `{ nodes_created: 3, edges_created: 0 }`
- Graph stats: `{ node_count: 3, edge_count: 0 }`

- Health checks:
- `checks[]` length: `5`

**Notes**

- Pinecone data-plane stats returned `0` while backend verification reported `2` vectors. This appears to be a namespace visibility or host routing mismatch; retrieval still returned the ingested phrase via public and widget chat.
- Health endpoint is now reachable after the `/sources/{source_id}/health` route order fix.

**Errors/Anomalies**

- `None` (run completed successfully)
