import pytest
from fastapi import HTTPException

from modules.interaction_context import (
    InteractionContext,
    require_owner_training_context,
    resolve_owner_chat_context,
    identity_gate_mode_for_context,
)


class DummyRequest:
    def __init__(self, training_session_id=None, metadata=None):
        self.training_session_id = training_session_id
        self.metadata = metadata


def test_owner_chat_default_context(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: None,
    )
    resolved = resolve_owner_chat_context(
        DummyRequest(),
        {"role": "owner", "user_id": "owner-1"},
        twin_id="twin-1",
    )
    assert resolved.context == InteractionContext.OWNER_CHAT
    assert identity_gate_mode_for_context(resolved.context) == "owner"


def test_owner_training_context_with_active_session(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: {"id": "ts-1", "status": "active", "owner_id": "owner-1"},
    )
    resolved = resolve_owner_chat_context(
        DummyRequest(training_session_id="ts-1"),
        {"role": "owner", "user_id": "owner-1"},
        twin_id="twin-1",
    )
    assert resolved.context == InteractionContext.OWNER_TRAINING
    assert resolved.training_session_id == "ts-1"


def test_owner_training_session_rejected_for_wrong_owner(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: {"id": "ts-2", "status": "active", "owner_id": "owner-2"},
    )
    with pytest.raises(HTTPException) as exc:
        resolve_owner_chat_context(
            DummyRequest(training_session_id="ts-2"),
            {"role": "owner", "user_id": "owner-1"},
            twin_id="twin-1",
        )
    assert exc.value.status_code == 403


def test_visitor_forced_to_public_widget(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: {"id": "ts-1", "status": "active", "owner_id": "owner-1"},
    )
    resolved = resolve_owner_chat_context(
        DummyRequest(training_session_id="ts-1"),
        {"role": "visitor"},
        twin_id="twin-1",
    )
    assert resolved.context == InteractionContext.PUBLIC_WIDGET
    assert identity_gate_mode_for_context(resolved.context) == "public"


def test_require_owner_training_context_accepts_active_training(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: {"id": "ts-1", "status": "active", "owner_id": "owner-1"},
    )
    resolved = require_owner_training_context(
        DummyRequest(training_session_id="ts-1"),
        {"role": "owner", "user_id": "owner-1"},
        twin_id="twin-1",
        action="decision capture",
    )
    assert resolved.context == InteractionContext.OWNER_TRAINING


def test_require_owner_training_context_rejects_owner_chat(monkeypatch):
    monkeypatch.setattr(
        "modules.interaction_context.get_training_session",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(HTTPException) as exc:
        require_owner_training_context(
            DummyRequest(training_session_id=None),
            {"role": "owner", "user_id": "owner-1"},
            twin_id="twin-1",
            action="decision capture",
        )
    assert exc.value.status_code == 403
