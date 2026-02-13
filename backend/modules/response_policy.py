"""
Shared response policy constants and helpers.

Keep uncertainty copy centralized so all chat surfaces present the same
trust message when evidence is insufficient.
"""

from __future__ import annotations

from modules.interaction_context import InteractionContext


UNCERTAINTY_RESPONSE = "I don't know based on available sources."


def owner_guidance_suffix(context: str | None) -> str:
    """
    Optional follow-up guidance for owner-facing contexts.
    Public contexts should not include owner training instructions.
    """
    if context in {
        InteractionContext.OWNER_CHAT.value,
        InteractionContext.OWNER_TRAINING.value,
    }:
        return " You can teach me by clarifying your stance or adding knowledge sources."
    return ""

