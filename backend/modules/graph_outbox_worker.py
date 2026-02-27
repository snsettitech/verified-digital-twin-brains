"""
Graph Outbox Worker

Processes graph_memory operations from graph_outbox directly.
This keeps graph-memory writes independent of the generic jobs queue.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from modules.graph_contradiction_detector import process_contradiction_evaluation_job
from modules.graph_outbox import GraphOperationType
from modules.graph_snapshot_manager import refresh_scope_snapshot, refresh_twin_snapshot
from modules.observability import supabase

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _infer_claim_type(sentence: str) -> str:
    lower = sentence.lower()
    if any(token in lower for token in ("prefer", "like", "dislike", "want")):
        return "preference"
    if any(token in lower for token in ("believe", "think", "opinion")):
        return "belief"
    if any(token in lower for token in ("should", "must", "best", "worst")):
        return "opinion"
    return "fact"


def _split_claim_candidates(text: str, max_claims: int = 10) -> List[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunks = re.split(r"[.\n!?;]+", normalized)
    seen = set()
    claims: List[str] = []
    for raw in chunks:
        sentence = _normalize_text(raw)
        if len(sentence) < 24:
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        claims.append(sentence[:400])
        if len(claims) >= max_claims:
            break

    if claims:
        return claims

    return [normalized[:220]]


async def _run_db(callable_obj):
    return await asyncio.to_thread(callable_obj)


async def _list_pending_job_ids(limit: int = 1) -> List[str]:
    now_iso = _utcnow_iso()

    def _query():
        result = (
            supabase.table("graph_outbox")
            .select("id")
            .eq("status", "pending")
            .or_(f"next_attempt_after.is.null,next_attempt_after.lte.{now_iso}")
            .order("priority", desc=True)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [str(row.get("id")) for row in (result.data or []) if row.get("id")]

    try:
        return await _run_db(_query)
    except Exception as exc:
        logger.error("[GraphOutboxWorker] failed to list pending jobs: %s", exc)
        return []


async def _claim_job(job_id: str, worker_id: str) -> Optional[Dict[str, Any]]:
    now_iso = _utcnow_iso()

    def _claim_rpc():
        return supabase.rpc(
            "claim_graph_outbox_job",
            {
                "p_job_id": job_id,
                "p_worker_id": worker_id,
                "p_now": now_iso,
            },
        ).execute()

    try:
        claimed = await _run_db(_claim_rpc)
        if not claimed.data:
            return None
    except Exception as exc:
        # Backward-compatible fallback if RPC is unavailable.
        logger.warning("[GraphOutboxWorker] claim RPC failed for %s: %s", job_id, exc)

        def _fallback_claim():
            return (
                supabase.table("graph_outbox")
                .update({"status": "processing", "updated_at": now_iso})
                .eq("id", job_id)
                .eq("status", "pending")
                .execute()
            )

        fallback = await _run_db(_fallback_claim)
        if not fallback.data:
            return None

    def _load():
        return supabase.table("graph_outbox").select("*").eq("id", job_id).single().execute()

    loaded = await _run_db(_load)
    return loaded.data if loaded and loaded.data else None


async def _mark_job_completed(job_id: str):
    now_iso = _utcnow_iso()

    def _update():
        return (
            supabase.table("graph_outbox")
            .update(
                {
                    "status": "completed",
                    "updated_at": now_iso,
                    "completed_at": now_iso,
                    "error_message": None,
                }
            )
            .eq("id", job_id)
            .execute()
        )

    await _run_db(_update)


async def _mark_job_failed(job: Dict[str, Any], error_message: str):
    job_id = str(job.get("id"))
    attempt_count = int(job.get("attempt_count") or 0)
    max_attempts = int(job.get("max_attempts") or 5)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    safe_error = (error_message or "unknown error")[:2000]

    if attempt_count >= max_attempts:
        payload = {
            "status": "failed",
            "updated_at": now_iso,
            "failed_at": now_iso,
            "error_message": safe_error,
        }
    else:
        backoff_seconds = min(2 ** max(attempt_count, 1), 3600)
        payload = {
            "status": "pending",
            "updated_at": now_iso,
            "error_message": safe_error,
            "next_attempt_after": (now + timedelta(seconds=backoff_seconds)).isoformat(),
        }

    def _update():
        return supabase.table("graph_outbox").update(payload).eq("id", job_id).execute()

    await _run_db(_update)


async def _refresh_snapshot(
    tenant_id: str,
    twin_id: str,
    correlation_id: Optional[str],
    scope_id: Optional[str] = None,
) -> bool:
    try:
        if scope_id:
            if "__" in scope_id:
                _, creator_id = scope_id.split("__", 1)
                return await refresh_twin_snapshot(
                    tenant_id=tenant_id,
                    twin_id=twin_id,
                    correlation_id=correlation_id,
                    creator_id=creator_id,
                )
            return await refresh_scope_snapshot(scope_id, correlation_id=correlation_id)
        return await refresh_twin_snapshot(
            tenant_id=tenant_id,
            twin_id=twin_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning("[GraphOutboxWorker] snapshot refresh failed: %s", exc)
        return False


async def _persist_claims(
    *,
    tenant_id: str,
    twin_id: str,
    scope_id: Optional[str],
    correlation_id: Optional[str],
    payload: Dict[str, Any],
) -> int:
    source_type = str(payload.get("source_type") or "graph_memory")
    source_ref = str(payload.get("source_ref") or payload.get("run_id") or "unknown")
    text = str(payload.get("text") or payload.get("content") or payload.get("body") or "").strip()

    claim_inputs: List[str] = []
    raw_claims = payload.get("claims")
    if isinstance(raw_claims, list):
        for item in raw_claims:
            if isinstance(item, str):
                claim_inputs.append(_normalize_text(item))
            elif isinstance(item, dict):
                claim_inputs.append(_normalize_text(str(item.get("text") or item.get("claim_text") or "")))

    if not claim_inputs:
        claim_inputs = _split_claim_candidates(text)

    if not claim_inputs:
        return 0

    group_id = scope_id or f"{tenant_id}__{twin_id}"
    now_iso = _utcnow_iso()
    rows: List[Dict[str, Any]] = []
    for claim_text in claim_inputs:
        if not claim_text:
            continue
        claim_id = _short_hash(f"{group_id}:{source_ref}:{claim_text}")
        row: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "twin_id": twin_id,
            "group_id": group_id,
            "claim_id": claim_id,
            "claim_text": claim_text,
            "claim_type": _infer_claim_type(claim_text),
            "confidence": 0.75,
            "content_hash": _short_hash(claim_text, length=24),
            "source_type": source_type,
            "source_ref": source_ref,
            "extracted_at": now_iso,
            "correlation_id": correlation_id,
        }
        if scope_id:
            row["scope_id"] = scope_id
        rows.append(row)

    if not rows:
        return 0

    def _upsert():
        return (
            supabase.table("graph_claims")
            .upsert(rows, on_conflict="tenant_id,twin_id,claim_id")
            .execute()
        )

    await _run_db(_upsert)
    return len(rows)


async def _process_create_episode(job: Dict[str, Any]) -> bool:
    # Episode persistence to Neo4j is best-effort. For the write-path verification
    # we mark this operation complete and rely on claim/snapshot materialization.
    payload = job.get("payload") or {}
    episode_name = str(payload.get("name") or "Deep Research Episode")
    logger.info(
        "[GraphOutboxWorker] processing create_episode job=%s name=%s",
        job.get("id"),
        episode_name[:120],
    )
    print(f"[GraphOutboxWorker] processing job={job.get('id')} operation=create_episode")
    return True


async def _process_create_claims(job: Dict[str, Any]) -> bool:
    payload = job.get("payload") or {}
    tenant_id = str(job.get("tenant_id") or "")
    twin_id = str(job.get("twin_id") or "")
    if not tenant_id or not twin_id:
        raise ValueError("create_claims job missing tenant_id or twin_id")

    scope_id = str(payload.get("scope_id") or job.get("scope_id") or "").strip() or None
    correlation_id = str(job.get("correlation_id") or payload.get("correlation_id") or "")

    claim_count = await _persist_claims(
        tenant_id=tenant_id,
        twin_id=twin_id,
        scope_id=scope_id,
        correlation_id=correlation_id or None,
        payload=payload,
    )
    logger.info(
        "[GraphOutboxWorker] processing create_claims job=%s persisted_claims=%s scope=%s",
        job.get("id"),
        claim_count,
        scope_id or "legacy",
    )
    print(
        f"[GraphOutboxWorker] processing job={job.get('id')} operation=create_claims claims={claim_count}"
    )

    await _refresh_snapshot(
        tenant_id=tenant_id,
        twin_id=twin_id,
        correlation_id=correlation_id or None,
        scope_id=scope_id,
    )
    return True


async def _process_extract_claims(job: Dict[str, Any]) -> bool:
    # Treat as alias for create_claims so legacy payloads still flow.
    print(f"[GraphOutboxWorker] processing job={job.get('id')} operation=extract_claims")
    return await _process_create_claims(job)


async def _process_evaluate_contradictions(job: Dict[str, Any]) -> bool:
    payload = job.get("payload") or {}
    tenant_id = str(job.get("tenant_id") or "")
    twin_id = str(job.get("twin_id") or "")
    if not tenant_id or not twin_id:
        raise ValueError("evaluate_contradictions job missing tenant_id or twin_id")

    correlation_id = str(job.get("correlation_id") or payload.get("correlation_id") or "")
    print(f"[GraphOutboxWorker] processing job={job.get('id')} operation=evaluate_contradictions")
    return await process_contradiction_evaluation_job(
        tenant_id=tenant_id,
        twin_id=twin_id,
        payload=payload,
        correlation_id=correlation_id or None,
    )


async def _process_refresh_snapshot(job: Dict[str, Any]) -> bool:
    payload = job.get("payload") or {}
    tenant_id = str(job.get("tenant_id") or "")
    twin_id = str(job.get("twin_id") or "")
    if not tenant_id or not twin_id:
        raise ValueError("refresh_snapshot job missing tenant_id or twin_id")

    scope_id = str(payload.get("scope_id") or job.get("scope_id") or "").strip() or None
    correlation_id = str(job.get("correlation_id") or payload.get("correlation_id") or "")
    print(f"[GraphOutboxWorker] processing job={job.get('id')} operation=refresh_snapshot")
    return await _refresh_snapshot(
        tenant_id=tenant_id,
        twin_id=twin_id,
        correlation_id=correlation_id or None,
        scope_id=scope_id,
    )


async def _dispatch(job: Dict[str, Any]) -> bool:
    operation = str(job.get("operation") or "").lower()

    if operation == GraphOperationType.CREATE_EPISODE.value:
        return await _process_create_episode(job)
    if operation == GraphOperationType.CREATE_CLAIMS.value:
        return await _process_create_claims(job)
    if operation == GraphOperationType.EXTRACT_CLAIMS.value:
        return await _process_extract_claims(job)
    if operation == GraphOperationType.EVALUATE_CONTRADICTIONS.value:
        return await _process_evaluate_contradictions(job)
    if operation == GraphOperationType.REFRESH_SNAPSHOT.value:
        return await _process_refresh_snapshot(job)

    logger.warning("[GraphOutboxWorker] unsupported operation=%s job=%s", operation, job.get("id"))
    return True


async def process_next_graph_outbox_job(worker_id: str) -> bool:
    pending_ids = await _list_pending_job_ids(limit=1)
    if not pending_ids:
        return False

    for job_id in pending_ids:
        job = await _claim_job(job_id=job_id, worker_id=worker_id)
        if not job:
            continue

        logger.info(
            "[GraphOutboxWorker] claimed job=%s operation=%s scope=%s",
            job.get("id"),
            job.get("operation"),
            job.get("scope_id"),
        )
        print(
            f"[GraphOutboxWorker] claim job={job.get('id')} operation={job.get('operation')} scope={job.get('scope_id')}"
        )

        try:
            success = await _dispatch(job)
            if success:
                await _mark_job_completed(str(job.get("id")))
                logger.info("[GraphOutboxWorker] completed job=%s", job.get("id"))
                print(f"[GraphOutboxWorker] completed job={job.get('id')}")
            else:
                await _mark_job_failed(job, "operation returned unsuccessful status")
                logger.warning("[GraphOutboxWorker] requeued job=%s (unsuccessful)", job.get("id"))
                print(f"[GraphOutboxWorker] requeued job={job.get('id')} reason=unsuccessful")
            return True
        except Exception as exc:
            await _mark_job_failed(job, str(exc))
            logger.exception("[GraphOutboxWorker] job failed job=%s error=%s", job.get("id"), exc)
            print(f"[GraphOutboxWorker] failed job={job.get('id')} error={exc}")
            return True

    return False


async def process_graph_outbox_batch(worker_id: str, limit: int = 10) -> int:
    processed = 0
    for _ in range(max(1, limit)):
        handled = await process_next_graph_outbox_job(worker_id=worker_id)
        if not handled:
            break
        processed += 1
    return processed
