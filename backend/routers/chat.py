"""ADK-first v2 chat routes."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from adk_core.app import get_conversation_repository
from adk_core.runtime import run_chat_turn, stream_chat_turn
from adk_core.schemas.api import ChatTurnRequest, ChatTurnResponse
from modules.auth_guard import ensure_twin_active, require_tenant, verify_twin_ownership
from modules.share_links import _fetch_twin_row, is_publicly_accessible_twin_record, validate_share_token

router = APIRouter(tags=["chat-v2"])


def _sse(event_type: str, payload: Dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


def _widget_access_or_404(twin_id: str) -> None:
    twin = _fetch_twin_row(twin_id)
    if not twin or not is_publicly_accessible_twin_record(twin):
        raise HTTPException(status_code=404, detail="Twin not found or widget access is disabled.")


def _public_access_or_404(twin_id: str, token: str) -> None:
    twin = _fetch_twin_row(twin_id)
    if not twin or not is_publicly_accessible_twin_record(twin) or not validate_share_token(token, twin_id):
        raise HTTPException(status_code=404, detail="Twin not found or public access is invalid.")


async def _stream_response(**kwargs: Any):
    async def generator():
        async for event in stream_chat_turn(**kwargs):
            event_type = str(event.get("type") or "message")
            yield _sse(event_type, event)

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/v2/chat/owner/{twin_id}", response_model=ChatTurnResponse)
async def owner_chat_turn(
    twin_id: str,
    request: ChatTurnRequest,
    user: dict = Depends(require_tenant),
) -> ChatTurnResponse:
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    return await run_chat_turn(
        twin_id=twin_id,
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        surface="owner",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
    )


@router.post("/v2/chat/owner/{twin_id}/stream")
async def owner_chat_stream(
    twin_id: str,
    request: ChatTurnRequest,
    user: dict = Depends(require_tenant),
):
    verify_twin_ownership(twin_id, user)
    ensure_twin_active(twin_id)
    return await _stream_response(
        twin_id=twin_id,
        tenant_id=user["tenant_id"],
        user_id=user["user_id"],
        surface="owner",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
    )


@router.post("/v2/chat/widget/{twin_id}", response_model=ChatTurnResponse)
async def widget_chat_turn(
    twin_id: str,
    request: ChatTurnRequest,
) -> ChatTurnResponse:
    _widget_access_or_404(twin_id)
    ensure_twin_active(twin_id)
    return await run_chat_turn(
        twin_id=twin_id,
        tenant_id=None,
        user_id=f"widget:{twin_id}",
        surface="widget",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
    )


@router.post("/v2/chat/widget/{twin_id}/stream")
async def widget_chat_stream(
    twin_id: str,
    request: ChatTurnRequest,
):
    _widget_access_or_404(twin_id)
    ensure_twin_active(twin_id)
    return await _stream_response(
        twin_id=twin_id,
        tenant_id=None,
        user_id=f"widget:{twin_id}",
        surface="widget",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
    )


@router.post("/v2/chat/public/{twin_id}/{token}", response_model=ChatTurnResponse)
async def public_chat_turn(
    twin_id: str,
    token: str,
    request: ChatTurnRequest,
) -> ChatTurnResponse:
    _public_access_or_404(twin_id, token)
    ensure_twin_active(twin_id)
    return await run_chat_turn(
        twin_id=twin_id,
        tenant_id=None,
        user_id=f"public:{twin_id}:{token[:8]}",
        surface="public",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
        share_token=token,
    )


@router.post("/v2/chat/public/{twin_id}/{token}/stream")
async def public_chat_stream(
    twin_id: str,
    token: str,
    request: ChatTurnRequest,
):
    _public_access_or_404(twin_id, token)
    ensure_twin_active(twin_id)
    return await _stream_response(
        twin_id=twin_id,
        tenant_id=None,
        user_id=f"public:{twin_id}:{token[:8]}",
        surface="public",
        message=request.message,
        conversation_id=request.conversation_id,
        client_context=request.client_context,
        share_token=token,
    )


@router.get("/v2/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    conversation = get_conversation_repository().get_conversation(conversation_id=conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.get("tenant_id") and str(conversation.get("tenant_id")) != str(user.get("tenant_id")):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.get("/v2/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: dict = Depends(require_tenant),
) -> Dict[str, Any]:
    conversation = get_conversation_repository().get_conversation(conversation_id=conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.get("tenant_id") and str(conversation.get("tenant_id")) != str(user.get("tenant_id")):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "conversation_id": conversation_id,
        "messages": get_conversation_repository().list_messages(conversation_id=conversation_id),
    }
