"""
Interaction Context Resolver

Derives immutable runtime context for each chat turn from trusted server signals.
Client-provided mode is never used for authorization decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from modules.training_sessions import get_training_session


class InteractionContext(str, Enum):
    OWNER_TRAINING = "owner_training"
    OWNER_CHAT = "owner_chat"
    PUBLIC_SHARE = "public_share"
    PUBLIC_WIDGET = "public_widget"


@dataclass(frozen=True)
class ResolvedInteractionContext:
    context: InteractionContext
    origin_endpoint: str
    share_link_id: Optional[str] = None
    training_session_id: Optional[str] = None

    @property
    def is_public(self) -> bool:
        return self.context in {InteractionContext.PUBLIC_SHARE, InteractionContext.PUBLIC_WIDGET}

    @property
    def can_write_training(self) -> bool:
        return self.context == InteractionContext.OWNER_TRAINING


def _coalesce_training_session_id(request_payload: Any) -> Optional[str]:
    # Accept explicit field first; allow metadata fallback for gradual rollout.
    training_session_id = getattr(request_payload, "training_session_id", None)
    if training_session_id:
        return training_session_id
    metadata = getattr(request_payload, "metadata", None) or {}
    if isinstance(metadata, dict):
        value = metadata.get("training_session_id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_owner_chat_context(
    request_payload: Any,
    user: Dict[str, Any],
    twin_id: str,
) -> ResolvedInteractionContext:
    """
    Resolve context for authenticated /chat/{twin_id} traffic.
    """
    role = (user or {}).get("role")
    if role == "visitor":
        return ResolvedInteractionContext(
            context=InteractionContext.PUBLIC_WIDGET,
            origin_endpoint="chat",
        )

    training_session_id = _coalesce_training_session_id(request_payload)
    if not training_session_id:
        return ResolvedInteractionContext(
            context=InteractionContext.OWNER_CHAT,
            origin_endpoint="chat",
        )

    session = get_training_session(training_session_id, twin_id=twin_id)
    if not session or session.get("status") != "active":
        return ResolvedInteractionContext(
            context=InteractionContext.OWNER_CHAT,
            origin_endpoint="chat",
        )

    owner_id = session.get("owner_id")
    user_id = (user or {}).get("user_id")
    if owner_id and user_id and owner_id != user_id:
        raise HTTPException(status_code=403, detail="Training session belongs to another owner")

    return ResolvedInteractionContext(
        context=InteractionContext.OWNER_TRAINING,
        origin_endpoint="chat",
        training_session_id=training_session_id,
    )


def resolve_widget_context() -> ResolvedInteractionContext:
    return ResolvedInteractionContext(
        context=InteractionContext.PUBLIC_WIDGET,
        origin_endpoint="chat-widget",
    )


def resolve_public_share_context(token: str) -> ResolvedInteractionContext:
    # Keep only a non-sensitive identifier in traces.
    share_link_id = (token or "")[:8] if token else None
    return ResolvedInteractionContext(
        context=InteractionContext.PUBLIC_SHARE,
        origin_endpoint="public-chat",
        share_link_id=share_link_id,
    )


def identity_gate_mode_for_context(context: InteractionContext) -> str:
    """
    Backward-compatible mode for the existing identity gate.
    """
    if context in {InteractionContext.PUBLIC_SHARE, InteractionContext.PUBLIC_WIDGET}:
        return "public"
    return "owner"


def clarification_mode_for_context(context: InteractionContext) -> str:
    """
    Backward-compatible clarification mode until DB constraint migration is applied.
    """
    if context in {InteractionContext.PUBLIC_SHARE, InteractionContext.PUBLIC_WIDGET}:
        return "public"
    return "owner"


def ensure_training_write_allowed(resolved: ResolvedInteractionContext, action: str) -> None:
    """
    Block training writes outside owner training context.
    """
    if resolved.can_write_training:
        return
    raise HTTPException(
        status_code=403,
        detail=f"{action} requires owner_training context",
    )


def require_owner_training_context(
    request_payload: Any,
    user: Dict[str, Any],
    twin_id: str,
    action: str,
) -> ResolvedInteractionContext:
    """
    Resolve context and enforce owner_training capability for training-write actions.
    """
    resolved = resolve_owner_chat_context(
        request_payload=request_payload,
        user=user,
        twin_id=twin_id,
    )
    ensure_training_write_allowed(resolved, action=action)
    return resolved


def trace_fields(resolved: ResolvedInteractionContext) -> Dict[str, Any]:
    return {
        "interaction_context": resolved.context.value,
        "origin_endpoint": resolved.origin_endpoint,
        "share_link_id": resolved.share_link_id,
        "training_session_id": resolved.training_session_id,
    }
