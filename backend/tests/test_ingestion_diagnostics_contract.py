"""
Contract tests for backend/modules/ingestion_diagnostics.py

These tests validate the public API surface of the ingestion diagnostics
module **without** touching Supabase or any external service.  They cover:

  - Enum membership and string coercion
  - build_error_dict structure and truncation
  - classify_youtube_error mapping for every known category
  - classify_linkedin_error mapping (login wall, rate limit, 4xx, 5xx, no-OG)
  - infer_provider URL classification
  - emit_step_event / persist_last_error / clear_last_error degrade
    gracefully when supabase is unreachable (they must never raise)
"""

# ---------------------------------------------------------------------------
# Ensure the backend package is importable
# ---------------------------------------------------------------------------
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# ---------------------------------------------------------------------------
# Import SUT
# ---------------------------------------------------------------------------

from modules.ingestion_diagnostics import (
    IngestionErrorCode,
    IngestionProvider,
    IngestionStep,
    StepStatus,
    build_error_dict,
    classify_linkedin_error,
    classify_youtube_error,
    clear_last_error,
    emit_step_event,
    get_source_events,
    infer_provider,
    persist_last_error,
)

# ====================================================================
# Enum tests
# ====================================================================


class TestIngestionStepEnum:
    """IngestionStep must contain all pipeline stages."""

    EXPECTED = {"fetch", "parse", "transcript", "chunk", "embed", "index"}

    def test_all_steps_present(self):
        values = {s.value for s in IngestionStep}
        assert values == self.EXPECTED

    def test_str_coercion(self):
        assert str(IngestionStep.FETCH) == "IngestionStep.FETCH"
        assert IngestionStep.FETCH.value == "fetch"

    def test_membership(self):
        assert IngestionStep("fetch") is IngestionStep.FETCH


class TestIngestionProviderEnum:
    """IngestionProvider must list every supported content source."""

    EXPECTED = {"youtube", "linkedin", "web", "file", "x", "rss", "podcast", "unknown"}

    def test_all_providers_present(self):
        values = {p.value for p in IngestionProvider}
        assert values == self.EXPECTED


class TestStepStatusEnum:
    EXPECTED = {"started", "completed", "failed", "skipped"}

    def test_all_statuses_present(self):
        values = {s.value for s in StepStatus}
        assert values == self.EXPECTED


# ====================================================================
# Error code constants
# ====================================================================


class TestIngestionErrorCode:
    """Verify that key error codes exist as class attributes."""

    REQUIRED_CODES = [
        # YouTube
        "YOUTUBE_FETCH_FAILED",
        "YOUTUBE_PARSE_FAILED",
        "YOUTUBE_TRANSCRIPT_UNAVAILABLE",
        "YOUTUBE_TRANSCRIPT_FETCH_FAILED",
        "YOUTUBE_AUTH_REQUIRED",
        "YOUTUBE_RATE_LIMITED",
        "YOUTUBE_GEO_BLOCKED",
        "YOUTUBE_VIDEO_UNAVAILABLE",
        "YOUTUBE_DOWNLOAD_FAILED",
        "YOUTUBE_TRANSCRIPTION_FAILED",
        # LinkedIn
        "LINKEDIN_BLOCKED_OR_REQUIRES_AUTH",
        "LINKEDIN_INVALID_URL",
        "LINKEDIN_FETCH_FAILED",
        "LINKEDIN_PARSE_FAILED",
        "LINKEDIN_NO_OG_DATA",
        "LINKEDIN_EXPORT_PARSE_FAILED",
        # Web
        "WEB_FETCH_FAILED",
        "WEB_PARSE_FAILED",
        "WEB_EMPTY_CONTENT",
        # File
        "FILE_READ_FAILED",
        "FILE_UNSUPPORTED_FORMAT",
        "FILE_EMPTY_CONTENT",
        # X
        "X_FETCH_FAILED",
        "X_AUTH_REQUIRED",
        "X_RATE_LIMITED",
        "X_PARSE_FAILED",
        # Generic
        "CHUNK_FAILED",
        "EMBED_FAILED",
        "INDEX_FAILED",
        "UNKNOWN_ERROR",
        "EMPTY_CONTENT",
        "TIMEOUT",
        "CREDENTIALS_MISSING",
    ]

    @pytest.mark.parametrize("code_name", REQUIRED_CODES)
    def test_code_exists(self, code_name):
        val = getattr(IngestionErrorCode, code_name, None)
        assert val is not None, f"Missing IngestionErrorCode.{code_name}"
        assert isinstance(val, str)
        # By convention the value equals the attribute name
        assert val == code_name


# ====================================================================
# build_error_dict
# ====================================================================


class TestBuildErrorDict:
    def test_minimal(self):
        d = build_error_dict(code="TEST_CODE", message="boom")
        assert d["code"] == "TEST_CODE"
        assert d["message"] == "boom"
        assert d["retryable"] is False
        # Optional keys absent when not provided
        assert "provider" not in d
        assert "step" not in d
        assert "http_status" not in d
        assert "raw" not in d

    def test_all_fields(self):
        d = build_error_dict(
            code="X",
            message="m",
            provider="youtube",
            step="fetch",
            http_status=429,
            provider_error_code="QUOTA_EXCEEDED",
            retryable=True,
            raw="very long text",
        )
        assert d["provider"] == "youtube"
        assert d["step"] == "fetch"
        assert d["http_status"] == 429
        assert d["provider_error_code"] == "QUOTA_EXCEEDED"
        assert d["retryable"] is True
        assert d["raw"] == "very long text"

    def test_raw_truncation(self):
        long_raw = "x" * 5000
        d = build_error_dict(code="C", message="m", raw=long_raw)
        assert len(d["raw"]) == 2000


# ====================================================================
# classify_youtube_error
# ====================================================================


class TestClassifyYoutubeError:
    """Each YouTube error category must map to the expected code."""

    @pytest.mark.parametrize(
        "error_msg, expected_code",
        [
            (
                "HTTP Error 429: Too Many Requests",
                IngestionErrorCode.YOUTUBE_RATE_LIMITED,
            ),
            ("rate limit exceeded", IngestionErrorCode.YOUTUBE_RATE_LIMITED),
            (
                "quota exceeded for this project",
                IngestionErrorCode.YOUTUBE_RATE_LIMITED,
            ),
            ("HTTP Error 403: Forbidden", IngestionErrorCode.YOUTUBE_AUTH_REQUIRED),
            ("Sign in to confirm your age", IngestionErrorCode.YOUTUBE_AUTH_REQUIRED),
            (
                "Video is not available in your region",
                IngestionErrorCode.YOUTUBE_GEO_BLOCKED,
            ),
            ("geo restriction applied", IngestionErrorCode.YOUTUBE_GEO_BLOCKED),
            ("This video is unavailable", IngestionErrorCode.YOUTUBE_VIDEO_UNAVAILABLE),
            ("Video has been deleted", IngestionErrorCode.YOUTUBE_VIDEO_UNAVAILABLE),
            ("Video not found", IngestionErrorCode.YOUTUBE_VIDEO_UNAVAILABLE),
            ("private video", IngestionErrorCode.YOUTUBE_VIDEO_UNAVAILABLE),
            (
                "No transcript available",
                IngestionErrorCode.YOUTUBE_TRANSCRIPT_UNAVAILABLE,
            ),
            (
                "Subtitles are disabled for this video",
                IngestionErrorCode.YOUTUBE_TRANSCRIPT_UNAVAILABLE,
            ),
            ("caption data missing", IngestionErrorCode.YOUTUBE_TRANSCRIPT_UNAVAILABLE),
            ("Connection timeout", IngestionErrorCode.YOUTUBE_FETCH_FAILED),
            ("socket error", IngestionErrorCode.YOUTUBE_FETCH_FAILED),
            ("Random unknown failure xyz", IngestionErrorCode.YOUTUBE_DOWNLOAD_FAILED),
        ],
    )
    def test_classification(self, error_msg, expected_code):
        result = classify_youtube_error(error_msg)
        assert result["code"] == expected_code, (
            f"'{error_msg}' → {result['code']} (expected {expected_code})"
        )
        # Every result must have these keys
        assert "message" in result
        assert "retryable" in result
        assert "step" in result

    def test_rate_limit_is_retryable(self):
        r = classify_youtube_error("HTTP Error 429: Too Many Requests")
        assert r["retryable"] is True

    def test_auth_is_not_retryable(self):
        r = classify_youtube_error("HTTP Error 403: Forbidden")
        assert r["retryable"] is False

    def test_network_is_retryable(self):
        r = classify_youtube_error("Connection timeout")
        assert r["retryable"] is True

    def test_unavailable_is_not_retryable(self):
        r = classify_youtube_error("This video is unavailable")
        assert r["retryable"] is False


# ====================================================================
# classify_linkedin_error
# ====================================================================


class TestClassifyLinkedinError:
    def test_login_wall_999(self):
        r = classify_linkedin_error(
            999, "Sign in to see all Sainath's connections. Join LinkedIn today."
        )
        assert r["code"] == IngestionErrorCode.LINKEDIN_BLOCKED_OR_REQUIRES_AUTH
        assert r["retryable"] is False
        assert r["http_status"] == 999
        assert "upload" in r["message"].lower() or "pdf" in r["message"].lower()

    def test_login_wall_403(self):
        r = classify_linkedin_error(403, "sign in to see this linkedin authwall page")
        assert r["code"] == IngestionErrorCode.LINKEDIN_BLOCKED_OR_REQUIRES_AUTH

    def test_login_wall_401(self):
        r = classify_linkedin_error(401, "anything")
        assert r["code"] == IngestionErrorCode.LINKEDIN_BLOCKED_OR_REQUIRES_AUTH

    def test_rate_limited(self):
        r = classify_linkedin_error(429, "")
        assert r["code"] == IngestionErrorCode.LINKEDIN_FETCH_FAILED
        assert r["retryable"] is True
        assert r["http_status"] == 429

    def test_server_error_retryable(self):
        r = classify_linkedin_error(502, "bad gateway")
        assert r["code"] == IngestionErrorCode.LINKEDIN_FETCH_FAILED
        assert r["retryable"] is True

    def test_client_error_not_retryable(self):
        r = classify_linkedin_error(400, "bad request")
        assert r["code"] == IngestionErrorCode.LINKEDIN_FETCH_FAILED
        assert r["retryable"] is False

    def test_no_og_data(self):
        r = classify_linkedin_error(200, "<html><body>Nothing useful</body></html>")
        assert r["code"] == IngestionErrorCode.LINKEDIN_NO_OG_DATA
        assert r["retryable"] is False
        assert (
            r["step"] == IngestionStep.PARSE.value or r["step"] == IngestionStep.PARSE
        )

    def test_message_always_present(self):
        for status_code in [200, 403, 429, 500, 999]:
            r = classify_linkedin_error(status_code, "")
            assert "message" in r
            assert len(r["message"]) > 0


# ====================================================================
# infer_provider
# ====================================================================


class TestInferProvider:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://www.youtube.com/watch?v=abc", IngestionProvider.YOUTUBE),
            ("https://youtu.be/abc", IngestionProvider.YOUTUBE),
            ("https://www.linkedin.com/in/someone/", IngestionProvider.LINKEDIN),
            ("https://linkedin.com/company/foo", IngestionProvider.LINKEDIN),
            ("https://twitter.com/user/status/123", IngestionProvider.X),
            ("https://x.com/user/status/123", IngestionProvider.X),
            ("https://example.com/blog/post", IngestionProvider.WEB),
            ("https://example.com/feed/rss", IngestionProvider.RSS),
            ("", IngestionProvider.UNKNOWN),
        ],
    )
    def test_infer(self, url, expected):
        assert infer_provider(url) == expected


# ====================================================================
# Graceful degradation — emit / persist / clear must never raise
# ====================================================================


class TestGracefulDegradation:
    """
    When Supabase is unreachable (mocked to raise), the diagnostics
    functions must swallow exceptions and return None / empty list.
    """

    def _mock_supabase_that_raises(self):
        """Return a mock supabase client where any .table() call raises."""
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("Supabase is down")
        return mock_sb

    def test_emit_step_event_returns_none_on_failure(self):
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=self._mock_supabase_that_raises(),
        ):
            result = emit_step_event(
                source_id="00000000-0000-0000-0000-000000000001",
                twin_id="00000000-0000-0000-0000-000000000002",
                provider=IngestionProvider.YOUTUBE,
                step=IngestionStep.FETCH,
                status=StepStatus.STARTED,
            )
            assert result is None  # degraded, not raised

    def test_persist_last_error_does_not_raise(self):
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=self._mock_supabase_that_raises(),
        ):
            # Must not raise
            persist_last_error(
                source_id="00000000-0000-0000-0000-000000000001",
                code=IngestionErrorCode.YOUTUBE_FETCH_FAILED,
                message="test error",
                provider=IngestionProvider.YOUTUBE,
                step=IngestionStep.FETCH,
            )

    def test_clear_last_error_does_not_raise(self):
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=self._mock_supabase_that_raises(),
        ):
            clear_last_error("00000000-0000-0000-0000-000000000001")

    def test_get_source_events_returns_empty_on_failure(self):
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=self._mock_supabase_that_raises(),
        ):
            result = get_source_events("00000000-0000-0000-0000-000000000001")
            assert result == []


# ====================================================================
# Happy-path DB interaction (mocked Supabase)
# ====================================================================


class TestEmitStepEventHappyPath:
    """Verify the correct Supabase calls are made when everything works."""

    def _build_mock_supabase(self):
        mock_sb = MagicMock()
        # .table("source_events").insert(...).execute()
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "event-1"}]
        mock_sb.table.return_value.insert.return_value.execute.return_value = (
            mock_insert_result
        )
        # .table("sources").update(...).eq(...).execute()
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "source-1"}]
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_result
        return mock_sb

    def test_inserts_event_and_updates_source(self):
        mock_sb = self._build_mock_supabase()
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=mock_sb,
        ):
            result = emit_step_event(
                source_id="src-1",
                twin_id="twin-1",
                provider=IngestionProvider.YOUTUBE,
                step=IngestionStep.FETCH,
                status=StepStatus.STARTED,
                metadata={"attempt": 1},
            )

        assert result == {"id": "event-1"}

        # Verify both table calls happened
        table_calls = [c.args[0] for c in mock_sb.table.call_args_list]
        assert "source_events" in table_calls
        assert "sources" in table_calls

    def test_completed_status_sets_ended_at(self):
        mock_sb = self._build_mock_supabase()
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=mock_sb,
        ):
            emit_step_event(
                source_id="src-1",
                twin_id="twin-1",
                provider="youtube",
                step="fetch",
                status=StepStatus.COMPLETED,
            )

        # The insert call's first positional arg is the row dict
        insert_call = mock_sb.table.return_value.insert.call_args
        row = insert_call[0][0] if insert_call[0] else insert_call[1].get("row", {})
        # ended_at should be set for COMPLETED status
        assert "ended_at" in row
        assert row["ended_at"] is not None


class TestPersistLastErrorHappyPath:
    def _build_mock_supabase(self):
        mock_sb = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "source-1"}]
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_result
        # For the _emit_failed_event_best_effort -> select twin_id lookup
        mock_select_result = MagicMock()
        mock_select_result.data = [{"twin_id": "twin-1"}]
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_select_result
        # For the inner emit_step_event insert
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "event-1"}]
        mock_sb.table.return_value.insert.return_value.execute.return_value = (
            mock_insert_result
        )
        return mock_sb

    def test_sets_source_status_error_by_default(self):
        mock_sb = self._build_mock_supabase()
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=mock_sb,
        ):
            persist_last_error(
                source_id="src-1",
                code=IngestionErrorCode.YOUTUBE_FETCH_FAILED,
                message="boom",
                provider=IngestionProvider.YOUTUBE,
                step=IngestionStep.FETCH,
                http_status=403,
                retryable=False,
                raw="raw detail",
            )

        # persist_last_error calls update() first, then _emit_failed_event_best_effort
        # calls emit_step_event which also calls update().  We need the FIRST update
        # call (from persist_last_error) — call_args returns the last one.
        all_update_calls = mock_sb.table.return_value.update.call_args_list
        assert len(all_update_calls) >= 1, "Expected at least one update call"
        first_update_call = all_update_calls[0]
        update_data = first_update_call[0][0] if first_update_call[0] else {}
        assert update_data.get("status") == "error"
        assert (
            update_data["last_error"]["code"] == IngestionErrorCode.YOUTUBE_FETCH_FAILED
        )
        assert update_data["last_error"]["http_status"] == 403
        assert update_data["last_error"]["retryable"] is False
        assert "last_error_at" in update_data

    def test_skip_source_status_when_flag_false(self):
        mock_sb = self._build_mock_supabase()
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=mock_sb,
        ):
            persist_last_error(
                source_id="src-1",
                code=IngestionErrorCode.EMBED_FAILED,
                message="embedding timeout",
                provider=IngestionProvider.FILE,
                step=IngestionStep.EMBED,
                set_source_status_error=False,
            )

        update_call = mock_sb.table.return_value.update.call_args
        update_data = update_call[0][0] if update_call[0] else {}
        assert "status" not in update_data


class TestClearLastErrorHappyPath:
    def test_clears_fields(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{}]
        )
        with patch(
            "modules.ingestion_diagnostics._get_supabase",
            return_value=mock_sb,
        ):
            clear_last_error("src-1")

        update_call = mock_sb.table.return_value.update.call_args
        update_data = update_call[0][0] if update_call[0] else {}
        assert update_data["last_error"] is None
        assert update_data["last_error_at"] is None
