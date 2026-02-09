"""
Persona Channel Isolation Checks

Reusable isolation/tamper checks for:
- owner/public context separation
- mode spoof prevention
- training-write authorization boundaries
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException

from modules.interaction_context import (
    InteractionContext,
    ResolvedInteractionContext,
    ensure_training_write_allowed,
    resolve_owner_chat_context,
    resolve_public_share_context,
)


DEFAULT_CHANNEL_CHECK_IDS: Tuple[str, ...] = (
    "owner_mode_spoof",
    "owner_active_training",
    "owner_inactive_training",
    "visitor_training_spoof",
    "public_share_resolution",
    "training_write_block_public",
)


@dataclass
class _FakePayload:
    training_session_id: Optional[str] = None
    mode: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def run_channel_isolation_checks(
    *,
    declared_checks: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Run deterministic interaction-context isolation checks.

    The checks intentionally monkeypatch `get_training_session` through the
    `modules.interaction_context` module to avoid DB dependency.
    """
    # Late import so monkeypatching this module doesn't alter global import time.
    import modules.interaction_context as interaction_context_module

    checks: List[Tuple[str, bool, str]] = []
    original_get_training_session = interaction_context_module.get_training_session

    try:
        # 1) Owner without training session stays owner_chat even if mode spoofed.
        resolved = resolve_owner_chat_context(
            request_payload=_FakePayload(training_session_id=None, mode="public"),
            user={"user_id": "owner-1", "role": "owner"},
            twin_id="twin-1",
        )
        checks.append(
            (
                "owner_mode_spoof",
                resolved.context == InteractionContext.OWNER_CHAT,
                resolved.context.value,
            )
        )

        # 2) Owner with active training session becomes owner_training.
        interaction_context_module.get_training_session = (
            lambda *_args, **_kwargs: {
                "id": "ts-1",
                "status": "active",
                "owner_id": "owner-1",
            }
        )
        resolved = resolve_owner_chat_context(
            request_payload=_FakePayload(training_session_id="ts-1"),
            user={"user_id": "owner-1", "role": "owner"},
            twin_id="twin-1",
        )
        checks.append(
            (
                "owner_active_training",
                resolved.context == InteractionContext.OWNER_TRAINING,
                resolved.context.value,
            )
        )

        # 3) Owner with inactive session falls back to owner_chat.
        interaction_context_module.get_training_session = (
            lambda *_args, **_kwargs: {
                "id": "ts-1",
                "status": "stopped",
                "owner_id": "owner-1",
            }
        )
        resolved = resolve_owner_chat_context(
            request_payload=_FakePayload(training_session_id="ts-1"),
            user={"user_id": "owner-1", "role": "owner"},
            twin_id="twin-1",
        )
        checks.append(
            (
                "owner_inactive_training",
                resolved.context == InteractionContext.OWNER_CHAT,
                resolved.context.value,
            )
        )

        # 4) Visitor cannot spoof training mode.
        interaction_context_module.get_training_session = (
            lambda *_args, **_kwargs: {
                "id": "ts-1",
                "status": "active",
                "owner_id": "owner-1",
            }
        )
        resolved = resolve_owner_chat_context(
            request_payload=_FakePayload(training_session_id="ts-1"),
            user={"user_id": None, "role": "visitor"},
            twin_id="twin-1",
        )
        checks.append(
            (
                "visitor_training_spoof",
                resolved.context == InteractionContext.PUBLIC_WIDGET,
                resolved.context.value,
            )
        )

        # 5) Public share context derivation is deterministic and non-sensitive.
        share_resolved = resolve_public_share_context("token-abcdef123")
        checks.append(
            (
                "public_share_resolution",
                share_resolved.context == InteractionContext.PUBLIC_SHARE
                and share_resolved.share_link_id == "token-ab",
                f"{share_resolved.context.value}:{share_resolved.share_link_id}",
            )
        )

        # 6) Training writes are blocked outside owner_training context.
        blocked_ok = False
        try:
            ensure_training_write_allowed(
                ResolvedInteractionContext(
                    context=InteractionContext.PUBLIC_SHARE,
                    origin_endpoint="public-chat",
                ),
                action="training write",
            )
        except HTTPException as exc:
            blocked_ok = exc.status_code == 403
        checks.append(("training_write_block_public", blocked_ok, "403 expected"))
    finally:
        interaction_context_module.get_training_session = original_get_training_session

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    executed_ids = sorted([check_id for check_id, _, _ in checks])
    declared = sorted(
        {
            str(item).strip()
            for item in (declared_checks if declared_checks is not None else DEFAULT_CHANNEL_CHECK_IDS)
            if str(item).strip()
        }
    )
    executed_set = set(executed_ids)
    declared_set = set(declared)

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round((passed / total) if total else 0.0, 4),
        "checks": [
            {"id": check_id, "passed": ok, "detail": detail}
            for check_id, ok, detail in checks
        ],
        "declared_checks": declared,
        "executed_checks": executed_ids,
        "undeclared_executed_checks": sorted(executed_set - declared_set),
        "missing_declared_checks": sorted(declared_set - executed_set),
    }

