"""
Ingestion Diagnostics Module
=============================
Shared enums, error codes, step-event emitter, and last_error persistence
for all ingestion paths (YouTube, LinkedIn, web, file, X/Twitter, RSS).

Every ingestion pipeline step emits a source_event row and keeps the
sources row's summary columns (last_step, last_provider, last_event_at,
last_error, last_error_at) up to date so the frontend can display
per-source diagnostics without joining into the events table.

Usage (inside any ingestion function):

    from modules.ingestion_diagnostics import (
        IngestionStep, IngestionProvider, IngestionErrorCode,
        emit_step_event, persist_last_error, clear_last_error,
    )

    emit_step_event(source_id, twin_id, IngestionProvider.YOUTUBE,
                    IngestionStep.FETCH, StepStatus.STARTED)
    try:
        ...
        emit_step_event(source_id, twin_id, IngestionProvider.YOUTUBE,
                        IngestionStep.FETCH, StepStatus.COMPLETED)
    except Exception as e:
        persist_last_error(
            source_id,
            code=IngestionErrorCode.YOUTUBE_FETCH_FAILED,
            message=str(e),
            provider=IngestionProvider.YOUTUBE,
            step=IngestionStep.FETCH,
            retryable=True,
        )
        raise
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IngestionStep(str, Enum):
    """Ordered steps in any ingestion pipeline."""

    FETCH = "fetch"
    PARSE = "parse"
    TRANSCRIPT = "transcript"  # YouTube / audio-specific
    CHUNK = "chunk"
    EMBED = "embed"
    INDEX = "index"


class IngestionProvider(str, Enum):
    """Content providers / source types."""

    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    WEB = "web"
    FILE = "file"
    X = "x"
    RSS = "rss"
    PODCAST = "podcast"
    UNKNOWN = "unknown"


class StepStatus(str, Enum):
    """Status values written to source_events.status."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Error codes — importable string constants so callers can do
#   code=IngestionErrorCode.YOUTUBE_TRANSCRIPT_UNAVAILABLE
# ---------------------------------------------------------------------------


class IngestionErrorCode:
    """
    Canonical error codes persisted in sources.last_error.code.

    Naming convention:  <PROVIDER>_<STEP>_<REASON>
    Generic codes omit the provider prefix.
    """

    # -- YouTube --
    YOUTUBE_FETCH_FAILED = "YOUTUBE_FETCH_FAILED"
    YOUTUBE_PARSE_FAILED = "YOUTUBE_PARSE_FAILED"
    YOUTUBE_TRANSCRIPT_UNAVAILABLE = "YOUTUBE_TRANSCRIPT_UNAVAILABLE"
    YOUTUBE_TRANSCRIPT_FETCH_FAILED = "YOUTUBE_TRANSCRIPT_FETCH_FAILED"
    YOUTUBE_AUTH_REQUIRED = "YOUTUBE_AUTH_REQUIRED"
    YOUTUBE_RATE_LIMITED = "YOUTUBE_RATE_LIMITED"
    YOUTUBE_GEO_BLOCKED = "YOUTUBE_GEO_BLOCKED"
    YOUTUBE_VIDEO_UNAVAILABLE = "YOUTUBE_VIDEO_UNAVAILABLE"
    YOUTUBE_DOWNLOAD_FAILED = "YOUTUBE_DOWNLOAD_FAILED"
    YOUTUBE_TRANSCRIPTION_FAILED = "YOUTUBE_TRANSCRIPTION_FAILED"

    # -- LinkedIn --
    LINKEDIN_BLOCKED_OR_REQUIRES_AUTH = "LINKEDIN_BLOCKED_OR_REQUIRES_AUTH"
    LINKEDIN_INVALID_URL = "LINKEDIN_INVALID_URL"
    LINKEDIN_FETCH_FAILED = "LINKEDIN_FETCH_FAILED"
    LINKEDIN_PARSE_FAILED = "LINKEDIN_PARSE_FAILED"
    LINKEDIN_NO_OG_DATA = "LINKEDIN_NO_OG_DATA"
    LINKEDIN_EXPORT_PARSE_FAILED = "LINKEDIN_EXPORT_PARSE_FAILED"

    # -- Web / URL --
    WEB_FETCH_FAILED = "WEB_FETCH_FAILED"
    WEB_PARSE_FAILED = "WEB_PARSE_FAILED"
    WEB_EMPTY_CONTENT = "WEB_EMPTY_CONTENT"

    # -- File --
    FILE_READ_FAILED = "FILE_READ_FAILED"
    FILE_UNSUPPORTED_FORMAT = "FILE_UNSUPPORTED_FORMAT"
    FILE_EMPTY_CONTENT = "FILE_EMPTY_CONTENT"

    # -- X / Twitter --
    X_FETCH_FAILED = "X_FETCH_FAILED"
    X_AUTH_REQUIRED = "X_AUTH_REQUIRED"
    X_RATE_LIMITED = "X_RATE_LIMITED"
    X_PARSE_FAILED = "X_PARSE_FAILED"

    # -- RSS / Podcast --
    RSS_FETCH_FAILED = "RSS_FETCH_FAILED"
    RSS_PARSE_FAILED = "RSS_PARSE_FAILED"

    # -- Generic (any provider) --
    CHUNK_FAILED = "CHUNK_FAILED"
    EMBED_FAILED = "EMBED_FAILED"
    INDEX_FAILED = "INDEX_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    EMPTY_CONTENT = "EMPTY_CONTENT"
    TIMEOUT = "TIMEOUT"
    CREDENTIALS_MISSING = "CREDENTIALS_MISSING"


# ---------------------------------------------------------------------------
# Supabase accessor — lazy, avoids circular import with observability.py
# ---------------------------------------------------------------------------

_supabase_client = None


def _get_supabase():
    """Return the shared Supabase client, imported lazily to avoid
    circular imports (observability imports clients, clients is imported
    everywhere)."""
    global _supabase_client
    if _supabase_client is None:
        from modules.observability import supabase as _sb

        _supabase_client = _sb
    return _supabase_client


# ---------------------------------------------------------------------------
# Helper: build a structured error dict
# ---------------------------------------------------------------------------


def build_error_dict(
    code: str,
    message: str,
    provider: Optional[str] = None,
    step: Optional[str] = None,
    http_status: Optional[int] = None,
    provider_error_code: Optional[str] = None,
    retryable: bool = False,
    raw: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalised error dict matching the JSONB schema in
    ``sources.last_error``.

    The ``raw`` field is truncated to 2000 chars to avoid bloating the
    DB row while still being useful for debugging.
    """
    err: Dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": retryable,
    }
    if provider is not None:
        err["provider"] = str(provider)
    if step is not None:
        err["step"] = str(step)
    if http_status is not None:
        err["http_status"] = http_status
    if provider_error_code is not None:
        err["provider_error_code"] = provider_error_code
    if raw is not None:
        err["raw"] = str(raw)[:2000]
    return err


# ---------------------------------------------------------------------------
# Public API: emit_step_event
# ---------------------------------------------------------------------------


def emit_step_event(
    source_id: str,
    twin_id: str,
    provider: IngestionProvider | str,
    step: IngestionStep | str,
    status: StepStatus | str,
    *,
    error: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    started_at: Optional[str] = None,
    ended_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Insert a row into ``source_events`` and update the summary
    columns on the ``sources`` row.

    This function is intentionally **fire-and-forget** — a failure to
    write diagnostics must never break the ingestion pipeline itself.
    All exceptions are caught, printed, and swallowed.

    Parameters
    ----------
    source_id : str
        UUID of the source being ingested.
    twin_id : str
        UUID of the owning twin.
    provider : IngestionProvider | str
        e.g. ``IngestionProvider.YOUTUBE`` or ``"youtube"``.
    step : IngestionStep | str
        e.g. ``IngestionStep.FETCH`` or ``"fetch"``.
    status : StepStatus | str
        e.g. ``StepStatus.COMPLETED`` or ``"completed"``.
    error : dict, optional
        Structured error dict (use :func:`build_error_dict`).
    metadata : dict, optional
        Arbitrary extra context to persist on the event row.
    started_at : str, optional
        ISO-8601 timestamp; defaults to ``now()``.
    ended_at : str, optional
        ISO-8601 timestamp; only meaningful for COMPLETED / FAILED.

    Returns
    -------
    dict or None
        The inserted ``source_events`` row, or ``None`` on failure.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    provider_str = str(provider.value if isinstance(provider, Enum) else provider)
    step_str = str(step.value if isinstance(step, Enum) else step)
    status_str = str(status.value if isinstance(status, Enum) else status)

    try:
        sb = _get_supabase()

        # 1. Insert into source_events
        event_row = {
            "source_id": source_id,
            "twin_id": twin_id,
            "provider": provider_str,
            "step": step_str,
            "status": status_str,
            "error": error,
            "metadata": metadata or {},
            "started_at": started_at or now_iso,
        }
        if ended_at:
            event_row["ended_at"] = ended_at
        elif status_str in (StepStatus.COMPLETED.value, StepStatus.FAILED.value):
            event_row["ended_at"] = now_iso

        insert_result = sb.table("source_events").insert(event_row).execute()

        # 2. Update sources summary columns
        update_data: Dict[str, Any] = {
            "last_provider": provider_str,
            "last_step": step_str,
            "last_event_at": now_iso,
        }
        sb.table("sources").update(update_data).eq("id", source_id).execute()

        return insert_result.data[0] if insert_result.data else None

    except Exception as exc:
        # Diagnostics must not break ingestion — degrade gracefully.
        print(
            f"[IngestionDiag] WARNING: emit_step_event failed for "
            f"source={source_id} step={step_str} status={status_str}: {exc}"
        )
        return None


# ---------------------------------------------------------------------------
# Public API: persist_last_error
# ---------------------------------------------------------------------------


def persist_last_error(
    source_id: str,
    code: str,
    message: str,
    provider: IngestionProvider | str,
    step: IngestionStep | str,
    *,
    http_status: Optional[int] = None,
    provider_error_code: Optional[str] = None,
    retryable: bool = False,
    raw: Optional[str] = None,
    set_source_status_error: bool = True,
) -> None:
    """Persist a structured error on the ``sources`` row and emit a
    corresponding ``FAILED`` step event.

    Like :func:`emit_step_event`, this is fire-and-forget.

    Parameters
    ----------
    source_id : str
        UUID of the source.
    code : str
        One of the :class:`IngestionErrorCode` constants.
    message : str
        Human-readable error description.
    provider : IngestionProvider | str
        Provider that encountered the error.
    step : IngestionStep | str
        The step that failed.
    http_status : int, optional
        HTTP status code from the upstream provider (e.g. 403, 429).
    provider_error_code : str, optional
        Provider-specific error code (e.g. YouTube error reason).
    retryable : bool
        Whether the caller believes a retry might succeed.
    raw : str, optional
        Raw/sanitised error detail (truncated to 2 KB).
    set_source_status_error : bool
        If ``True`` (default), also sets ``sources.status = 'error'``.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    provider_str = str(provider.value if isinstance(provider, Enum) else provider)
    step_str = str(step.value if isinstance(step, Enum) else step)

    error_obj = build_error_dict(
        code=code,
        message=message,
        provider=provider_str,
        step=step_str,
        http_status=http_status,
        provider_error_code=provider_error_code,
        retryable=retryable,
        raw=raw,
    )

    try:
        sb = _get_supabase()

        update_data: Dict[str, Any] = {
            "last_error": error_obj,
            "last_error_at": now_iso,
            "last_provider": provider_str,
            "last_step": step_str,
            "last_event_at": now_iso,
        }
        if set_source_status_error:
            update_data["status"] = "error"

        sb.table("sources").update(update_data).eq("id", source_id).execute()

    except Exception as exc:
        print(
            f"[IngestionDiag] WARNING: persist_last_error failed for "
            f"source={source_id} code={code}: {exc}"
        )

    # Also emit a FAILED step event (best-effort, uses its own try/except)
    # We pass the twin_id as empty-string sentinel — the event insert will
    # still succeed in Supabase if twin_id FK is present on the row via the
    # source_id cascade.  Callers that have twin_id should use
    # emit_step_event directly before calling persist_last_error.
    _emit_failed_event_best_effort(source_id, provider_str, step_str, error_obj)


# ---------------------------------------------------------------------------
# Public API: clear_last_error
# ---------------------------------------------------------------------------


def clear_last_error(source_id: str) -> None:
    """Clear the ``last_error`` fields on a source row.

    Typically called at the start of a retry so stale errors don't
    linger if the retry succeeds.
    """
    try:
        sb = _get_supabase()
        sb.table("sources").update(
            {
                "last_error": None,
                "last_error_at": None,
            }
        ).eq("id", source_id).execute()
    except Exception as exc:
        print(
            f"[IngestionDiag] WARNING: clear_last_error failed for "
            f"source={source_id}: {exc}"
        )


# ---------------------------------------------------------------------------
# Public API: get_source_events
# ---------------------------------------------------------------------------


def get_source_events(
    source_id: str,
    limit: int = 50,
) -> list[Dict[str, Any]]:
    """Return the most recent step events for a source, newest first.

    Used by the ``GET /sources/{source_id}/events`` endpoint and the
    UI diagnostics drawer.
    """
    try:
        sb = _get_supabase()
        res = (
            sb.table("source_events")
            .select("*")
            .eq("source_id", source_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data if res.data else []
    except Exception as exc:
        print(
            f"[IngestionDiag] WARNING: get_source_events failed for "
            f"source={source_id}: {exc}"
        )
        return []


# ---------------------------------------------------------------------------
# Public API: classify_youtube_error
# ---------------------------------------------------------------------------


def classify_youtube_error(error_msg: str) -> Dict[str, Any]:
    """Map a raw YouTube / yt-dlp error string to a structured
    ``(code, message, retryable, step)`` dict.

    This extends the existing ``ErrorClassifier`` in ``ingestion.py``
    with the new diagnostic code system.
    """
    err = error_msg.lower()

    # Rate limiting
    if (
        "429" in error_msg
        or "rate" in err
        or "quota" in err
        or "too many requests" in err
    ):
        return {
            "code": IngestionErrorCode.YOUTUBE_RATE_LIMITED,
            "message": "YouTube rate limit reached. Retrying with backoff.",
            "retryable": True,
            "step": IngestionStep.FETCH,
        }

    # Auth / 403
    if (
        "403" in error_msg
        or "sign in" in err
        or "unauthorized" in err
        or "login" in err
    ):
        return {
            "code": IngestionErrorCode.YOUTUBE_AUTH_REQUIRED,
            "message": "This video requires authentication or is age-restricted.",
            "retryable": False,
            "step": IngestionStep.FETCH,
        }

    # Geo/region blocking
    if "geo" in err or "region" in err or "not available in your" in err:
        return {
            "code": IngestionErrorCode.YOUTUBE_GEO_BLOCKED,
            "message": "This video is not available in your region.",
            "retryable": False,
            "step": IngestionStep.FETCH,
        }

    # Video unavailable
    if (
        "unavailable" in err
        or "deleted" in err
        or "not found" in err
        or "private" in err
    ):
        return {
            "code": IngestionErrorCode.YOUTUBE_VIDEO_UNAVAILABLE,
            "message": "This video is unavailable (deleted, private, or not found).",
            "retryable": False,
            "step": IngestionStep.FETCH,
        }

    # Transcript / captions specific
    if "transcript" in err or "caption" in err or "subtitles" in err:
        return {
            "code": IngestionErrorCode.YOUTUBE_TRANSCRIPT_UNAVAILABLE,
            "message": "No captions/transcript available for this video.",
            "retryable": False,
            "step": IngestionStep.TRANSCRIPT,
        }

    # Network
    if "timeout" in err or "connection" in err or "socket" in err or "network" in err:
        return {
            "code": IngestionErrorCode.YOUTUBE_FETCH_FAILED,
            "message": "Network error while contacting YouTube. Retrying.",
            "retryable": True,
            "step": IngestionStep.FETCH,
        }

    # Fallback
    return {
        "code": IngestionErrorCode.YOUTUBE_DOWNLOAD_FAILED,
        "message": f"YouTube download failed: {error_msg[:200]}",
        "retryable": False,
        "step": IngestionStep.FETCH,
    }


# ---------------------------------------------------------------------------
# Public API: classify_linkedin_error
# ---------------------------------------------------------------------------


def classify_linkedin_error(
    status_code: Optional[int],
    body_text: str,
) -> Dict[str, Any]:
    """Classify a LinkedIn OG-fetch response into a structured error.

    Returns a dict with ``code``, ``message``, ``retryable``, ``step``,
    and ``http_status``.
    """
    body_lower = (body_text or "").lower()

    # Explicit login wall detection
    login_cues = (
        "sign in" in body_lower
        and "linkedin" in body_lower
        and (
            "join linkedin" in body_lower
            or "sign in to see" in body_lower
            or "authwall" in body_lower
        )
    )

    if login_cues or status_code in (401, 403, 999):
        return {
            "code": IngestionErrorCode.LINKEDIN_BLOCKED_OR_REQUIRES_AUTH,
            "message": (
                "LinkedIn blocked this request or requires authentication. "
                "Upload your LinkedIn profile PDF export or paste your profile text instead."
            ),
            "retryable": False,
            "step": IngestionStep.FETCH,
            "http_status": status_code,
        }

    if status_code == 429:
        return {
            "code": IngestionErrorCode.LINKEDIN_FETCH_FAILED,
            "message": "LinkedIn rate limited this request. Try again later.",
            "retryable": True,
            "step": IngestionStep.FETCH,
            "http_status": 429,
        }

    if status_code and status_code >= 400:
        return {
            "code": IngestionErrorCode.LINKEDIN_FETCH_FAILED,
            "message": f"LinkedIn returned HTTP {status_code}.",
            "retryable": status_code >= 500,
            "step": IngestionStep.FETCH,
            "http_status": status_code,
        }

    # Successful HTTP but no usable OG data
    return {
        "code": IngestionErrorCode.LINKEDIN_NO_OG_DATA,
        "message": (
            "Could not extract profile data from LinkedIn page. "
            "Upload your LinkedIn profile PDF export or paste your profile text instead."
        ),
        "retryable": False,
        "step": IngestionStep.PARSE,
        "http_status": status_code,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _emit_failed_event_best_effort(
    source_id: str,
    provider_str: str,
    step_str: str,
    error_obj: Dict[str, Any],
) -> None:
    """Try to insert a FAILED source_event.  If the twin_id is not
    readily available we look it up from the sources row."""
    try:
        sb = _get_supabase()
        # Resolve twin_id from sources row
        src_res = (
            sb.table("sources").select("twin_id").eq("id", source_id).limit(1).execute()
        )
        twin_id = src_res.data[0]["twin_id"] if src_res.data else None
        if not twin_id:
            return

        emit_step_event(
            source_id=source_id,
            twin_id=twin_id,
            provider=provider_str,
            step=step_str,
            status=StepStatus.FAILED,
            error=error_obj,
        )
    except Exception as exc:
        print(
            f"[IngestionDiag] WARNING: _emit_failed_event_best_effort "
            f"failed for source={source_id}: {exc}"
        )


# ---------------------------------------------------------------------------
# Convenience: infer provider from URL
# ---------------------------------------------------------------------------


def infer_provider(url: str) -> IngestionProvider:
    """Best-effort provider classification from a URL string."""
    if not url:
        return IngestionProvider.UNKNOWN
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return IngestionProvider.YOUTUBE
    if "linkedin.com" in url_lower:
        return IngestionProvider.LINKEDIN
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return IngestionProvider.X
    if url_lower.endswith((".rss", "/feed", "/rss")) or "feed" in url_lower:
        return IngestionProvider.RSS
    return IngestionProvider.WEB
