from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from modules.auth_guard import ensure_twin_active, verify_owner, verify_twin_ownership
from modules.observability import supabase
from modules.realtime_ingestion import (
    RealtimeIngestionError,
    append_realtime_event,
    commit_realtime_session,
    enqueue_realtime_processing_job,
    get_realtime_session,
    list_realtime_events,
    mark_realtime_session_committed,
    process_realtime_session,
    realtime_schema_status,
    start_realtime_session,
)
from modules.realtime_stream_queue import get_realtime_stream_metrics


router = APIRouter(tags=["ingestion-realtime"])


class RealtimeSessionStartRequest(BaseModel):
    source_type: str = "realtime_stream"
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RealtimeSessionAppendRequest(BaseModel):
    sequence_no: int = Field(..., ge=0)
    text_chunk: str = ""
    event_type: str = "transcript_partial"
    metadata: Optional[Dict[str, Any]] = None
    process_now: bool = False
    enqueue_when_ready: bool = True


class RealtimeSessionCommitRequest(BaseModel):
    metadata: Optional[Dict[str, Any]] = None
    process_async: bool = True


class RealtimeSessionProcessRequest(BaseModel):
    force: bool = True


def _ensure_session_access_or_403(session: Dict[str, Any], user: Dict[str, Any]) -> None:
    twin_id = str(session.get("twin_id"))
    verify_twin_ownership(twin_id, user)

    session_tenant = session.get("tenant_id")
    user_tenant = user.get("tenant_id")
    if session_tenant and user_tenant and str(session_tenant) != str(user_tenant):
        raise HTTPException(status_code=403, detail="Session tenant mismatch")

    session_owner = session.get("owner_id")
    user_id = user.get("user_id")
    if session_owner and user_id and str(session_owner) != str(user_id):
        raise HTTPException(status_code=403, detail="Session owner mismatch")


@router.post("/ingest/realtime/sessions/{twin_id}/start")
async def start_realtime_session_endpoint(
    twin_id: str,
    request: RealtimeSessionStartRequest,
    user=Depends(verify_owner),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)

    try:
        session = start_realtime_session(
            twin_id=twin_id,
            owner_id=user.get("user_id"),
            tenant_id=user.get("tenant_id"),
            source_type=request.source_type,
            title=request.title,
            metadata=request.metadata or {},
        )
        return {"status": "active", "session": session}
    except RealtimeIngestionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/realtime/sessions/{session_id}/append")
async def append_realtime_session_event_endpoint(
    session_id: str,
    request: RealtimeSessionAppendRequest,
    http_req: Request,
    user=Depends(verify_owner),
):
    session = get_realtime_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    _ensure_session_access_or_403(session, user)
    ensure_twin_active(str(session.get("twin_id")))

    correlation_id = http_req.headers.get("x-correlation-id") or http_req.headers.get("x-request-id")

    try:
        append_result = append_realtime_event(
            session_id=session_id,
            sequence_no=request.sequence_no,
            text_chunk=request.text_chunk,
            event_type=request.event_type,
            metadata=request.metadata,
        )

        processing = None
        queued_job = None
        queue_error = None
        if request.process_now:
            processing = await process_realtime_session(
                session_id=session_id,
                force=False,
                correlation_id=correlation_id,
            )
        elif request.enqueue_when_ready and append_result.get("should_index"):
            try:
                queued_job = enqueue_realtime_processing_job(
                    session_id=session_id,
                    twin_id=str(session.get("twin_id")),
                    force=False,
                    reason="threshold",
                )
            except Exception as queue_exc:
                queue_error = str(queue_exc)
                # Degrade gracefully if queue path is unavailable.
                processing = await process_realtime_session(
                    session_id=session_id,
                    force=False,
                    correlation_id=correlation_id,
                )

        return {
            "status": append_result.get("status", "appended"),
            "append": append_result,
            "processing": processing,
            "queued_job": queued_job,
            "queue_error": queue_error,
        }
    except RealtimeIngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/realtime/sessions/{session_id}/process")
async def process_realtime_session_endpoint(
    session_id: str,
    request: RealtimeSessionProcessRequest,
    http_req: Request,
    user=Depends(verify_owner),
):
    session = get_realtime_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    _ensure_session_access_or_403(session, user)
    ensure_twin_active(str(session.get("twin_id")))

    correlation_id = http_req.headers.get("x-correlation-id") or http_req.headers.get("x-request-id")
    try:
        result = await process_realtime_session(
            session_id=session_id,
            force=bool(request.force),
            correlation_id=correlation_id,
        )
        return {"status": "ok", "result": result}
    except RealtimeIngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/realtime/sessions/{session_id}/commit")
async def commit_realtime_session_endpoint(
    session_id: str,
    request: RealtimeSessionCommitRequest,
    http_req: Request,
    user=Depends(verify_owner),
):
    session = get_realtime_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    _ensure_session_access_or_403(session, user)
    ensure_twin_active(str(session.get("twin_id")))

    correlation_id = http_req.headers.get("x-correlation-id") or http_req.headers.get("x-request-id")
    try:
        if request.process_async:
            updated = mark_realtime_session_committed(
                session_id=session_id,
                metadata=request.metadata or {},
            )
            try:
                queued_job = enqueue_realtime_processing_job(
                    session_id=session_id,
                    twin_id=str(session.get("twin_id")),
                    force=True,
                    reason="commit",
                )
                return {"status": "committed_queued", "session": updated, "queued_job": queued_job}
            except Exception as queue_exc:
                # Best-effort fallback to inline processing if async queue path is not ready.
                processing = await process_realtime_session(
                    session_id=session_id,
                    force=True,
                    correlation_id=correlation_id,
                )
                return {
                    "status": "committed_processed_fallback",
                    "session": updated,
                    "processing": processing,
                    "queue_error": str(queue_exc),
                }

        result = await commit_realtime_session(
            session_id=session_id,
            metadata=request.metadata or {},
            correlation_id=correlation_id,
        )
        return {"status": "committed", **result}
    except RealtimeIngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/realtime/sessions/{session_id}")
async def get_realtime_session_endpoint(
    session_id: str,
    user=Depends(verify_owner),
):
    session = get_realtime_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    _ensure_session_access_or_403(session, user)

    try:
        count_res = (
            supabase.table("ingestion_stream_events")
            .select("id", count="exact")
            .eq("session_id", session_id)
            .execute()
        )
        event_count = int(count_res.count or 0)
    except Exception:
        event_count = 0

    return {
        "session": session,
        "event_count": event_count,
        "indexing_lag_chars": int(session.get("appended_chars") or 0) - int(session.get("indexed_chars") or 0),
    }


@router.get("/ingest/realtime/sessions/{session_id}/events")
async def get_realtime_session_events_endpoint(
    session_id: str,
    after_sequence_no: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    stream: bool = Query(False),
    poll_seconds: int = Query(30, ge=5, le=300),
    user=Depends(verify_owner),
):
    session = get_realtime_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Realtime session not found")
    _ensure_session_access_or_403(session, user)

    if not stream:
        events = list_realtime_events(
            session_id=session_id,
            after_sequence_no=after_sequence_no,
            limit=limit,
        )
        return {
            "session_id": session_id,
            "after_sequence_no": after_sequence_no,
            "events": events,
        }

    async def _event_stream():
        last_seq = after_sequence_no
        start = time.time()
        heartbeat_at = start

        while True:
            events = list_realtime_events(
                session_id=session_id,
                after_sequence_no=last_seq,
                limit=limit,
            )
            if events:
                for event in events:
                    last_seq = max(last_seq, int(event.get("sequence_no") or 0))
                    payload = {"type": "event", "event": event}
                    yield f"data: {json.dumps(payload)}\n\n"

            current = get_realtime_session(session_id)
            if not current:
                yield f"data: {json.dumps({'type': 'error', 'detail': 'session_not_found'})}\n\n"
                break

            if current.get("status") in {"committed", "failed", "cancelled"}:
                yield f"data: {json.dumps({'type': 'session', 'status': current.get('status')})}\n\n"
                break

            now = time.time()
            if now - heartbeat_at >= 5:
                yield f"data: {json.dumps({'type': 'heartbeat', 'last_sequence_no': last_seq})}\n\n"
                heartbeat_at = now

            if now - start >= poll_seconds:
                break

            await asyncio.sleep(1)

        yield f"data: {json.dumps({'type': 'done', 'last_sequence_no': last_seq})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/ingest/realtime/health")
async def realtime_ingestion_health():
    ok, err = realtime_schema_status()
    return {
        "status": "healthy" if ok else "degraded",
        "schema_available": bool(ok),
        "error": err,
    }


@router.get("/ingest/realtime/stream-metrics")
async def realtime_stream_metrics(user=Depends(verify_owner)):
    # Owner-authenticated diagnostics endpoint.
    return get_realtime_stream_metrics()
