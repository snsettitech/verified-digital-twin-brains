"""
Phase 5 realtime ingestion primitives.

Implements an append/commit model for stream-based ingestion without AssemblyAI:
- session lifecycle management
- ordered, idempotent event append
- replayable event log
- periodic/full indexing into existing ingestion pipeline
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.delphi_namespace import resolve_creator_id_for_twin
from modules.ingestion import process_and_index_text
from modules.job_queue import enqueue_job
from modules.jobs import JobType, append_log, complete_job, create_job, fail_job, start_job
from modules.observability import log_ingestion_event, supabase
from modules.realtime_stream_queue import publish_realtime_job


REALTIME_MIN_CHARS_DELTA = int(os.getenv("REALTIME_MIN_CHARS_DELTA", "1200"))
REALTIME_MIN_SECONDS_BETWEEN_INDEX = int(os.getenv("REALTIME_MIN_SECONDS_BETWEEN_INDEX", "10"))
REALTIME_JOB_PRIORITY = int(os.getenv("REALTIME_JOB_PRIORITY", "1"))


class RealtimeIngestionError(RuntimeError):
    """Raised when realtime ingestion operations fail."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def realtime_schema_status() -> Tuple[bool, Optional[str]]:
    """
    Return whether realtime ingestion schema is available.
    """
    try:
        supabase.table("ingestion_stream_sessions").select("id").limit(1).execute()
        supabase.table("ingestion_stream_events").select("id").limit(1).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def _ensure_schema_or_raise() -> None:
    ok, err = realtime_schema_status()
    if ok:
        return
    raise RealtimeIngestionError(
        "Realtime ingestion schema unavailable. Apply "
        "backend/database/migrations/20260213_phase5_realtime_ingestion.sql. "
        f"Details: {err}"
    )


def create_realtime_source_row(
    *,
    source_id: str,
    twin_id: str,
    filename: str,
    source_type: str = "realtime_stream",
) -> Dict[str, Any]:
    payload = {
        "id": source_id,
        "twin_id": twin_id,
        "filename": filename,
        "file_size": 0,
        "content_text": "",
        "status": "processing",
        "staging_status": "staged",
        "health_status": "healthy",
        "citation_url": None,
        "type": source_type,
    }
    try:
        res = supabase.table("sources").insert(payload).execute()
    except Exception as e:
        # Compatibility fallback for DBs where `sources.type` is not migrated.
        if "type" in str(e).lower() and "column" in str(e).lower():
            fallback = dict(payload)
            fallback.pop("type", None)
            res = supabase.table("sources").insert(fallback).execute()
        else:
            raise

    if not res.data:
        raise RealtimeIngestionError("Failed to create source row for realtime session")
    return res.data[0]


def get_realtime_session(session_id: str) -> Optional[Dict[str, Any]]:
    _ensure_schema_or_raise()
    try:
        res = (
            supabase.table("ingestion_stream_sessions")
            .select("*")
            .eq("id", session_id)
            .single()
            .execute()
        )
        return res.data if res.data else None
    except Exception:
        return None


def start_realtime_session(
    *,
    twin_id: str,
    owner_id: Optional[str],
    tenant_id: Optional[str],
    source_type: str = "realtime_stream",
    title: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_schema_or_raise()

    session_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    started_at = _utc_now_iso()
    creator_id = resolve_creator_id_for_twin(twin_id)

    session_title = (title or "").strip() or f"Realtime Stream {started_at}"
    source_row = create_realtime_source_row(
        source_id=source_id,
        twin_id=twin_id,
        filename=session_title,
        source_type=source_type,
    )

    payload = {
        "id": session_id,
        "twin_id": twin_id,
        "tenant_id": tenant_id,
        "creator_id": creator_id,
        "owner_id": owner_id,
        "source_id": source_id,
        "status": "active",
        "source_type": source_type,
        "metadata": {
            "title": session_title,
            **(metadata or {}),
        },
        "last_sequence_no": 0,
        "appended_chars": 0,
        "indexed_chars": 0,
        "started_at": started_at,
    }

    res = supabase.table("ingestion_stream_sessions").insert(payload).execute()
    if not res.data:
        raise RealtimeIngestionError("Failed to create realtime ingestion session")
    session = res.data[0]
    session["source"] = source_row
    return session


def list_realtime_events(
    *,
    session_id: str,
    after_sequence_no: int = 0,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    _ensure_schema_or_raise()
    query = (
        supabase.table("ingestion_stream_events")
        .select("*")
        .eq("session_id", session_id)
        .order("sequence_no", desc=False)
        .limit(limit)
    )
    if after_sequence_no > 0:
        query = query.gt("sequence_no", after_sequence_no)
    res = query.execute()
    return res.data or []


def _merge_event_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    return dict(metadata)


def _is_duplicate_event_error(error: Exception) -> bool:
    msg = str(error).lower()
    return (
        "duplicate key" in msg
        or "unique constraint" in msg
        or "uq_ingestion_stream_events_session_sequence" in msg
    )


def _should_incremental_index(
    *,
    session: Dict[str, Any],
    force: bool = False,
) -> bool:
    if force:
        return True

    appended_chars = int(session.get("appended_chars") or 0)
    indexed_chars = int(session.get("indexed_chars") or 0)
    chars_delta = appended_chars - indexed_chars
    if chars_delta < REALTIME_MIN_CHARS_DELTA:
        return False

    last_indexed_at = _parse_iso(session.get("last_indexed_at"))
    if not last_indexed_at:
        return True

    now = datetime.now(timezone.utc)
    elapsed = (now - last_indexed_at).total_seconds()
    return elapsed >= REALTIME_MIN_SECONDS_BETWEEN_INDEX


def append_realtime_event(
    *,
    session_id: str,
    sequence_no: int,
    text_chunk: str,
    event_type: str = "transcript_partial",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_schema_or_raise()

    session = get_realtime_session(session_id)
    if not session:
        raise RealtimeIngestionError("Realtime session not found")
    if session.get("status") != "active":
        raise RealtimeIngestionError("Realtime session is not active")

    text_chunk = text_chunk or ""
    chars_count = len(text_chunk)
    event_payload = {
        "session_id": session_id,
        "sequence_no": int(sequence_no),
        "event_type": event_type,
        "text_chunk": text_chunk,
        "chars_count": chars_count,
        "metadata": _merge_event_metadata(metadata),
    }

    duplicate = False
    try:
        res = supabase.table("ingestion_stream_events").insert(event_payload).execute()
        event = res.data[0] if res.data else event_payload
    except Exception as e:
        if not _is_duplicate_event_error(e):
            raise
        duplicate = True
        existing = (
            supabase.table("ingestion_stream_events")
            .select("*")
            .eq("session_id", session_id)
            .eq("sequence_no", sequence_no)
            .single()
            .execute()
        )
        event = existing.data if existing.data else event_payload

    if not duplicate:
        updated_last_sequence = max(int(session.get("last_sequence_no") or 0), int(sequence_no))
        updated_chars = int(session.get("appended_chars") or 0) + chars_count
        supabase.table("ingestion_stream_sessions").update(
            {
                "last_sequence_no": updated_last_sequence,
                "appended_chars": updated_chars,
            }
        ).eq("id", session_id).execute()
        session["last_sequence_no"] = updated_last_sequence
        session["appended_chars"] = updated_chars

    return {
        "status": "duplicate" if duplicate else "appended",
        "session": session,
        "event": event,
        "should_index": _should_incremental_index(session=session),
    }


def _build_session_text(session_id: str) -> str:
    events = list_realtime_events(session_id=session_id, after_sequence_no=0, limit=100000)
    text_parts: List[str] = []
    for event in events:
        if event.get("event_type") not in {"transcript_partial", "transcript_final", "text"}:
            continue
        chunk = (event.get("text_chunk") or "").strip()
        if chunk:
            text_parts.append(chunk)
    return "\n".join(text_parts).strip()


async def process_realtime_session(
    *,
    session_id: str,
    force: bool = False,
    provider: str = "realtime_stream",
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure_schema_or_raise()

    session = get_realtime_session(session_id)
    if not session:
        raise RealtimeIngestionError("Realtime session not found")

    if session.get("status") not in {"active", "committed"}:
        return {"processed": False, "reason": f"session_status={session.get('status')}"}

    if not _should_incremental_index(session=session, force=force):
        return {"processed": False, "reason": "threshold_not_reached"}

    twin_id = str(session.get("twin_id"))
    source_id = str(session.get("source_id") or "")
    if not source_id:
        raise RealtimeIngestionError("Realtime session has no source_id")

    combined_text = _build_session_text(session_id)
    if not combined_text:
        return {"processed": False, "reason": "no_text"}

    metadata = session.get("metadata") or {}
    filename = (metadata.get("title") or f"Realtime Stream {session_id}")[:200]

    chunks = await process_and_index_text(
        source_id=source_id,
        twin_id=twin_id,
        text=combined_text,
        metadata_override={
            "filename": filename,
            "type": "realtime_stream",
            "stream_session_id": session_id,
        },
        provider=provider,
        correlation_id=correlation_id,
    )

    now_iso = _utc_now_iso()
    text_len = len(combined_text)
    supabase.table("sources").update(
        {
            "content_text": combined_text,
            "file_size": text_len,
            "extracted_text_length": text_len,
            "chunk_count": chunks,
            "status": "live",
            "staging_status": "live",
        }
    ).eq("id", source_id).execute()

    supabase.table("ingestion_stream_sessions").update(
        {
            "indexed_chars": text_len,
            "last_indexed_at": now_iso,
        }
    ).eq("id", session_id).execute()

    log_ingestion_event(
        source_id=source_id,
        twin_id=twin_id,
        level="info",
        message=f"Realtime session indexed ({chunks} chunks)",
        metadata={"session_id": session_id, "indexed_chars": text_len},
    )

    return {
        "processed": True,
        "session_id": session_id,
        "source_id": source_id,
        "chunks": chunks,
        "indexed_chars": text_len,
    }


def mark_realtime_session_committed(
    *,
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Mark session as committed without running indexing inline.
    """
    _ensure_schema_or_raise()
    session = get_realtime_session(session_id)
    if not session:
        raise RealtimeIngestionError("Realtime session not found")
    if session.get("status") == "committed":
        return session
    if session.get("status") != "active":
        raise RealtimeIngestionError(f"Cannot commit session with status={session.get('status')}")

    merged_metadata = dict(session.get("metadata") or {})
    merged_metadata.update(metadata or {})
    committed_at = _utc_now_iso()
    res = (
        supabase.table("ingestion_stream_sessions")
        .update(
            {
                "status": "committed",
                "metadata": merged_metadata,
                "committed_at": committed_at,
            }
        )
        .eq("id", session_id)
        .execute()
    )
    return res.data[0] if res.data else get_realtime_session(session_id)


def _job_matches_session(job: Dict[str, Any], session_id: str) -> bool:
    metadata = job.get("metadata") or {}
    return str(metadata.get("session_id") or "") == str(session_id)


def _find_inflight_realtime_job(session_id: str, twin_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            supabase.table("jobs")
            .select("id,status,metadata,priority")
            .eq("twin_id", twin_id)
            .eq("job_type", JobType.REALTIME_INGESTION.value)
            .in_("status", ["queued", "processing"])
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        for row in res.data or []:
            if _job_matches_session(row, session_id):
                return row
        return None
    except Exception:
        return None


def enqueue_realtime_processing_job(
    *,
    session_id: str,
    twin_id: str,
    force: bool = False,
    reason: str = "threshold",
    priority: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Enqueue async realtime indexing with dedupe.
    """
    _ensure_schema_or_raise()
    existing = _find_inflight_realtime_job(session_id=session_id, twin_id=twin_id)
    if existing:
        return {
            "enqueued": False,
            "reason": "job_already_inflight",
            "job_id": existing.get("id"),
            "status": existing.get("status"),
        }

    job_priority = REALTIME_JOB_PRIORITY if priority is None else int(priority)
    metadata = {
        "session_id": session_id,
        "force": bool(force),
        "trigger_reason": reason,
    }

    stream_mode = "legacy_queue"
    try:
        job = create_job(
            job_type=JobType.REALTIME_INGESTION,
            twin_id=twin_id,
            source_id=None,
            priority=job_priority,
            metadata=metadata,
        )
        stream_message_id = publish_realtime_job(
            job_id=job.id,
            session_id=session_id,
            twin_id=twin_id,
            force=bool(force),
            reason=reason,
        )
        if not stream_message_id:
            # Legacy fallback path when streams are unavailable.
            enqueue_job(job.id, JobType.REALTIME_INGESTION.value, priority=job_priority, metadata=metadata)
        else:
            stream_mode = "redis_streams"
            # Persist trace metadata for observability.
            supabase.table("jobs").update(
                {
                    "metadata": {
                        **metadata,
                        "stream_message_id": stream_message_id,
                        "stream_mode": "redis_streams",
                    }
                }
            ).eq("id", job.id).execute()
    except Exception as e:
        raise RealtimeIngestionError(f"Failed to enqueue realtime ingestion job: {e}") from e

    return {
        "enqueued": True,
        "job_id": job.id,
        "priority": job_priority,
        "stream_mode": stream_mode,
    }


async def process_realtime_job(job_id: str) -> bool:
    """
    Worker handler for realtime_ingestion jobs.
    """
    try:
        job_res = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
        job = job_res.data or {}
    except Exception as e:
        print(f"[RealtimeIngestion] job lookup failed for {job_id}: {e}")
        return False

    if not job:
        print(f"[RealtimeIngestion] job {job_id} not found")
        return False

    metadata = dict(job.get("metadata") or {})
    session_id = str(metadata.get("session_id") or "").strip()
    force = bool(metadata.get("force", False))

    if not session_id:
        fail_job(job_id, "Missing session_id in job metadata")
        return False

    try:
        start_job(job_id)
    except Exception:
        # Job may already be marked processing by dequeue claim.
        pass

    append_log(job_id, f"Processing realtime ingestion session={session_id}, force={force}")

    try:
        result = await process_realtime_session(
            session_id=session_id,
            force=force,
            provider="realtime_stream_async",
        )
        complete_job(job_id, metadata={"realtime_result": result})
        append_log(job_id, f"Realtime ingestion finished: {result}")
        return True
    except Exception as e:
        fail_job(job_id, f"Realtime ingestion failed: {e}")
        append_log(job_id, f"Realtime ingestion failed: {e}", log_level="error")
        return False


async def commit_realtime_session(
    *,
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    provider: str = "realtime_stream",
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    _ensure_schema_or_raise()
    session = get_realtime_session(session_id)
    if not session:
        raise RealtimeIngestionError("Realtime session not found")

    if session.get("status") == "committed":
        return {"session": session, "processing": {"processed": False, "reason": "already_committed"}}
    if session.get("status") != "active":
        raise RealtimeIngestionError(f"Cannot commit session with status={session.get('status')}")

    processing = await process_realtime_session(
        session_id=session_id,
        force=True,
        provider=provider,
        correlation_id=correlation_id,
    )

    merged_metadata = dict(session.get("metadata") or {})
    merged_metadata.update(metadata or {})
    committed_at = _utc_now_iso()
    res = (
        supabase.table("ingestion_stream_sessions")
        .update(
            {
                "status": "committed",
                "metadata": merged_metadata,
                "committed_at": committed_at,
            }
        )
        .eq("id", session_id)
        .execute()
    )
    updated = res.data[0] if res.data else get_realtime_session(session_id)
    return {"session": updated, "processing": processing}
