"""
Phase 5 Redis Streams queue for realtime ingestion jobs.

Best-practice goals:
- consumer groups (at-least-once delivery)
- explicit ACK after successful processing
- stale message recovery via XAUTOCLAIM
- graceful fallback when Redis is unavailable
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, Tuple

from modules.job_queue import get_redis_client


REALTIME_USE_REDIS_STREAMS = os.getenv("REALTIME_USE_REDIS_STREAMS", "true").lower() == "true"
REALTIME_STREAM_NAME = os.getenv("REALTIME_STREAM_NAME", "realtime_ingestion_stream")
REALTIME_STREAM_GROUP = os.getenv("REALTIME_STREAM_GROUP", "realtime_workers")
REALTIME_STREAM_BLOCK_MS = int(os.getenv("REALTIME_STREAM_BLOCK_MS", "1000"))
REALTIME_STREAM_READ_COUNT = int(os.getenv("REALTIME_STREAM_READ_COUNT", "10"))
REALTIME_STREAM_MIN_IDLE_MS = int(os.getenv("REALTIME_STREAM_MIN_IDLE_MS", "30000"))
REALTIME_STREAM_MAXLEN = int(os.getenv("REALTIME_STREAM_MAXLEN", "50000"))


def streams_available() -> bool:
    return REALTIME_USE_REDIS_STREAMS and get_redis_client() is not None


def _ensure_group(client) -> None:
    try:
        client.xgroup_create(
            name=REALTIME_STREAM_NAME,
            groupname=REALTIME_STREAM_GROUP,
            id="0",
            mkstream=True,
        )
    except Exception as e:
        msg = str(e).lower()
        if "busygroup" in msg:
            return
        raise


def publish_realtime_job(
    *,
    job_id: str,
    session_id: str,
    twin_id: str,
    force: bool = False,
    reason: str = "threshold",
) -> Optional[str]:
    """
    Publish a realtime processing job to Redis Streams.

    Returns:
        message_id when published, otherwise None.
    """
    if not REALTIME_USE_REDIS_STREAMS:
        return None

    client = get_redis_client()
    if not client:
        return None

    _ensure_group(client)
    fields = {
        "job_id": str(job_id),
        "session_id": str(session_id),
        "twin_id": str(twin_id),
        "force": "1" if force else "0",
        "reason": str(reason),
        "enqueued_at_unix": str(int(time.time())),
    }
    msg_id = client.xadd(
        REALTIME_STREAM_NAME,
        fields,
        maxlen=REALTIME_STREAM_MAXLEN,
        approximate=True,
    )
    return msg_id


def _normalize_stream_fields(fields: Dict[Any, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for k, v in (fields or {}).items():
        key = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
        value = v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
        normalized[key] = value
    return normalized


def _normalize_message_id(message_id: Any) -> str:
    if isinstance(message_id, (bytes, bytearray)):
        return message_id.decode("utf-8")
    return str(message_id)


def _read_new_messages(client, consumer_id: str):
    return client.xreadgroup(
        groupname=REALTIME_STREAM_GROUP,
        consumername=consumer_id,
        streams={REALTIME_STREAM_NAME: ">"},
        count=REALTIME_STREAM_READ_COUNT,
        block=REALTIME_STREAM_BLOCK_MS,
    )


def _read_stale_messages(client, consumer_id: str):
    # Claim stale pending messages from dead consumers.
    # Returns: (next_start_id, [(id, fields), ...])
    try:
        next_start, claimed = client.xautoclaim(
            name=REALTIME_STREAM_NAME,
            groupname=REALTIME_STREAM_GROUP,
            consumername=consumer_id,
            min_idle_time=REALTIME_STREAM_MIN_IDLE_MS,
            start_id="0-0",
            count=REALTIME_STREAM_READ_COUNT,
        )
        return next_start, claimed
    except Exception:
        return None, []


def dequeue_realtime_stream_job(consumer_id: str) -> Optional[Dict[str, Any]]:
    """
    Read one realtime ingestion job from stream group.

    Returns dict:
    {
      "stream_message_id": "...",
      "job_id": "...",
      "job_type": "realtime_ingestion",
      "metadata": {...}
    }
    """
    if not streams_available():
        return None

    client = get_redis_client()
    if not client:
        return None

    _ensure_group(client)

    # 1) read new messages
    try:
        entries = _read_new_messages(client, consumer_id)
    except Exception:
        return None

    if entries:
        _, messages = entries[0]
        if messages:
            msg_id, fields = messages[0]
            msg_id = _normalize_message_id(msg_id)
            fields = _normalize_stream_fields(fields)
            return {
                "stream_message_id": msg_id,
                "job_id": fields.get("job_id"),
                "job_type": "realtime_ingestion",
                "metadata": {
                    "session_id": fields.get("session_id"),
                    "twin_id": fields.get("twin_id"),
                    "force": fields.get("force") == "1",
                    "reason": fields.get("reason"),
                    "stream_enqueued_at_unix": fields.get("enqueued_at_unix"),
                },
            }

    # 2) claim stale pending
    _next_start, claimed = _read_stale_messages(client, consumer_id)
    if claimed:
        msg_id, fields = claimed[0]
        msg_id = _normalize_message_id(msg_id)
        fields = _normalize_stream_fields(fields)
        return {
            "stream_message_id": msg_id,
            "job_id": fields.get("job_id"),
            "job_type": "realtime_ingestion",
            "metadata": {
                "session_id": fields.get("session_id"),
                "twin_id": fields.get("twin_id"),
                "force": fields.get("force") == "1",
                "reason": fields.get("reason"),
                "stream_enqueued_at_unix": fields.get("enqueued_at_unix"),
                "claimed_stale": True,
            },
        }

    return None


def ack_realtime_stream_message(message_id: str) -> bool:
    if not streams_available() or not message_id:
        return False
    client = get_redis_client()
    if not client:
        return False
    try:
        client.xack(REALTIME_STREAM_NAME, REALTIME_STREAM_GROUP, message_id)
        # Optional cleanup to reduce stream growth pressure.
        client.xdel(REALTIME_STREAM_NAME, message_id)
        return True
    except Exception:
        return False


def get_realtime_stream_metrics() -> Dict[str, Any]:
    """
    Basic stream health metrics for diagnostics dashboards.
    """
    metrics = {
        "enabled": bool(REALTIME_USE_REDIS_STREAMS),
        "available": False,
        "stream": REALTIME_STREAM_NAME,
        "group": REALTIME_STREAM_GROUP,
        "pending": None,
        "consumers": None,
    }
    client = get_redis_client()
    if not (REALTIME_USE_REDIS_STREAMS and client):
        return metrics

    metrics["available"] = True
    try:
        _ensure_group(client)
        groups = client.xinfo_groups(REALTIME_STREAM_NAME) or []
        group_info = None
        for g in groups:
            name = g.get("name")
            if isinstance(name, (bytes, bytearray)):
                name = name.decode("utf-8")
            if name == REALTIME_STREAM_GROUP:
                group_info = g
                break
        if group_info:
            metrics["pending"] = int(group_info.get("pending", 0))
            metrics["consumers"] = int(group_info.get("consumers", 0))
    except Exception as e:
        metrics["error"] = str(e)
    return metrics
