from datetime import datetime, timedelta, timezone

from modules import training_sessions


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_active_session_expired_when_older_than_ttl(monkeypatch):
    monkeypatch.setenv("TRAINING_SESSION_TTL_MINUTES", "60")
    started = datetime.now(timezone.utc) - timedelta(hours=2)
    session = {"status": "active", "started_at": _iso_utc(started)}
    assert training_sessions._is_active_session_expired(session) is True


def test_active_session_not_expired_when_within_ttl(monkeypatch):
    monkeypatch.setenv("TRAINING_SESSION_TTL_MINUTES", "240")
    started = datetime.now(timezone.utc) - timedelta(minutes=30)
    session = {"status": "active", "started_at": _iso_utc(started)}
    assert training_sessions._is_active_session_expired(session) is False


def test_non_active_session_never_expires(monkeypatch):
    monkeypatch.setenv("TRAINING_SESSION_TTL_MINUTES", "5")
    started = datetime.now(timezone.utc) - timedelta(days=3)
    session = {"status": "stopped", "started_at": _iso_utc(started)}
    assert training_sessions._is_active_session_expired(session) is False

