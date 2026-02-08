#!/usr/bin/env python3
"""
Dev-only proof helper for LinkedIn + YouTube ingestion evidence.

What it does:
- Reads latest `sources` rows for the required test URLs.
- Reads `chunks` counts for those source IDs.
- Queries Pinecone namespace for each twin using a probe phrase.
- Writes a JSON artifact under docs/ingestion/proof_outputs/.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from modules.embeddings import get_embedding  # noqa: E402
from modules.clients import get_pinecone_index  # noqa: E402

YOUTUBE_URL = "https://www.youtube.com/watch?v=HiC1J8a9V1I"
LINKEDIN_URL = "https://www.linkedin.com/in/sainathsetti/"


def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(BACKEND_ROOT / ".env")


def _required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _latest_source_for_url(supabase_client, url: str) -> Optional[Dict[str, Any]]:
    res = (
        supabase_client.table("sources")
        .select(
            "id,twin_id,status,filename,citation_url,chunk_count,created_at,updated_at,"
            "last_provider,last_step,last_error,last_error_at,last_event_at"
        )
        .eq("citation_url", url)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def _chunk_count_for_source(supabase_client, source_id: str) -> int:
    res = (
        supabase_client.table("chunks")
        .select("id", count="exact")
        .eq("source_id", source_id)
        .limit(1)
        .execute()
    )
    return int(res.count or 0)


def _probe_phrase(source: Dict[str, Any], fallback: str) -> str:
    # Build a stable phrase likely to be present in metadata/text.
    filename = (source.get("filename") or "").strip()
    if filename:
        return filename[:120]
    return fallback


def _pinecone_proof(twin_id: str, phrase: str) -> Dict[str, Any]:
    index = get_pinecone_index()
    stats = index.describe_index_stats()

    query_embedding = get_embedding(phrase)
    query = index.query(
        vector=query_embedding,
        top_k=3,
        include_metadata=True,
        namespace=twin_id,
    )

    matches: List[Dict[str, Any]] = []
    for item in query.get("matches", []) or []:
        metadata = item.get("metadata", {}) or {}
        matches.append(
            {
                "id": item.get("id"),
                "score": item.get("score"),
                "source_id": metadata.get("source_id"),
                "filename": metadata.get("filename"),
                "text_preview": (metadata.get("text") or "")[:240],
            }
        )

    namespaces = stats.get("namespaces", {}) or {}
    namespace_count = 0
    if twin_id in namespaces:
        namespace_count = int((namespaces.get(twin_id) or {}).get("vector_count", 0))

    return {
        "phrase": phrase,
        "namespace_vector_count": namespace_count,
        "matches": matches,
    }


def main() -> int:
    _load_env()

    supabase_url = _required_env("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or _required_env("SUPABASE_KEY")
    supabase_client = create_client(supabase_url, supabase_key)

    result: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "youtube_url": YOUTUBE_URL,
            "linkedin_url": LINKEDIN_URL,
        },
        "sources": {},
        "pinecone": {},
    }

    errors: List[str] = []

    try:
        youtube_source = _latest_source_for_url(supabase_client, YOUTUBE_URL)
    except Exception as exc:
        youtube_source = None
        errors.append(f"Failed querying YouTube source: {exc}")

    try:
        linkedin_source = _latest_source_for_url(supabase_client, LINKEDIN_URL)
    except Exception as exc:
        linkedin_source = None
        errors.append(f"Failed querying LinkedIn source: {exc}")

    result["sources"]["youtube"] = youtube_source
    result["sources"]["linkedin"] = linkedin_source

    if youtube_source and youtube_source.get("id"):
        try:
            result["sources"]["youtube_chunk_rows"] = _chunk_count_for_source(supabase_client, youtube_source["id"])
        except Exception as exc:
            result["sources"]["youtube_chunk_rows"] = 0
            errors.append(f"Failed querying YouTube chunks: {exc}")
    else:
        result["sources"]["youtube_chunk_rows"] = 0

    if linkedin_source and linkedin_source.get("id"):
        try:
            result["sources"]["linkedin_chunk_rows"] = _chunk_count_for_source(supabase_client, linkedin_source["id"])
        except Exception as exc:
            result["sources"]["linkedin_chunk_rows"] = 0
            errors.append(f"Failed querying LinkedIn chunks: {exc}")
    else:
        result["sources"]["linkedin_chunk_rows"] = 0

    # Pinecone proof for each source namespace if available.
    if youtube_source and youtube_source.get("twin_id"):
        try:
            phrase = _probe_phrase(
                youtube_source,
                fallback="One of the biggest questions right now",
            )
            result["pinecone"]["youtube"] = _pinecone_proof(youtube_source["twin_id"], phrase)
        except Exception as exc:
            errors.append(f"Failed Pinecone YouTube proof: {exc}")

    if linkedin_source and linkedin_source.get("twin_id"):
        try:
            phrase = _probe_phrase(
                linkedin_source,
                fallback="LinkedIn Profile public metadata",
            )
            result["pinecone"]["linkedin"] = _pinecone_proof(linkedin_source["twin_id"], phrase)
        except Exception as exc:
            errors.append(f"Failed Pinecone LinkedIn proof: {exc}")

    if errors:
        result["errors"] = errors

    out_dir = REPO_ROOT / "docs" / "ingestion" / "proof_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"proof_linkedin_youtube_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(result, indent=2, default=_json_default), encoding="utf-8")

    print(f"Wrote proof artifact: {out_path}")
    print(json.dumps(result, indent=2, default=_json_default)[:4000])
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
