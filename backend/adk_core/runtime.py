"""Execution helpers and event translation for the ADK runtime."""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import HTTPException, status
from google.genai import types

from adk_core.agents.persona_responder import PERSONA_RESPONDER_NAME
from adk_core.app import (
    get_chat_runner,
    get_compiler_runner,
    get_conversation_repository,
    get_persona_repository,
    get_research_repository,
    get_research_runner,
    get_session_service,
)
from adk_core.schemas.api import ChatTurnResponse
from adk_core.schemas.artifacts import PersonaArtifact, ResearchArtifact


def _text_from_event(event: Any) -> str:
    if not getattr(event, "content", None) or not getattr(event.content, "parts", None):
        return ""
    parts = []
    for part in event.content.parts:
        if getattr(part, "text", None):
            parts.append(part.text)
    return "".join(parts)


def _json_list(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if item]
        except Exception:
            return [raw]
    return []


async def _ensure_session(
    *,
    app_name: str,
    session_id: str,
    user_id: str,
    state: Dict[str, Any],
) -> None:
    session = await get_session_service().get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if session is None:
        await get_session_service().create_session(
            app_name=app_name,
            user_id=user_id,
            state=state,
            session_id=session_id,
        )


async def run_research_pipeline(
    *,
    run_id: str,
    tenant_id: str,
    user_id: str,
    subject_name: str,
    twin_id: Optional[str] = None,
    hints: Optional[Dict[str, Any]] = None,
) -> ResearchArtifact:
    research_repository = get_research_repository()
    research_repository.update_run(run_id, status="running", error_message=None)

    hints = hints or {}
    state = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "run_id": run_id,
        "twin_id": twin_id,
        "subject_name": subject_name,
        "research_location": hints.get("location", ""),
        "research_company": hints.get("company", ""),
        "research_website": hints.get("website", ""),
    }

    await _ensure_session(
        app_name="adk_research",
        session_id=run_id,
        user_id=user_id,
        state=state,
    )

    try:
        async for _event in get_research_runner().run_async(
            user_id=user_id,
            session_id=run_id,
            new_message=types.Content(role="user", parts=[types.Part(text=f"Research {subject_name}")]),
        ):
            pass

        session = await get_session_service().get_session(
            app_name="adk_research",
            user_id=user_id,
            session_id=run_id,
        )
        if not session:
            raise RuntimeError("Research session missing after execution.")
        artifact_json = session.state.get("research_artifact_json")
        if not artifact_json:
            raise RuntimeError("Research pipeline did not produce research_artifact_json.")
        artifact = ResearchArtifact.model_validate_json(artifact_json)
        research_repository.save_artifact(
            run_id=run_id,
            tenant_id=tenant_id,
            twin_id=twin_id,
            artifact=artifact.model_dump(mode="json"),
        )
        research_repository.update_run(run_id, status="completed", error_message=None)
        return artifact
    except Exception as exc:
        research_repository.update_run(run_id, status="failed", error_message=str(exc))
        raise


async def run_compiler_pipeline(
    *,
    run_id: str,
    tenant_id: str,
    twin_id: str,
    user_id: str,
    research_artifact: ResearchArtifact,
    publish: bool = True,
) -> Dict[str, Any]:
    persona_repository = get_persona_repository()
    session_id = f"{run_id}:{twin_id}:compile"
    state = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "run_id": run_id,
        "twin_id": twin_id,
        "research_artifact_json": research_artifact.model_dump_json(),
    }
    await _ensure_session(
        app_name="adk_compiler",
        session_id=session_id,
        user_id=user_id,
        state=state,
    )

    async for _event in get_compiler_runner().run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=f"Compile persona for {twin_id}")]),
    ):
        pass

    session = await get_session_service().get_session(
        app_name="adk_compiler",
        user_id=user_id,
        session_id=session_id,
    )
    if not session:
        raise RuntimeError("Compiler session missing after execution.")
    artifact_json = session.state.get("persona_artifact_json") or session.state.get("persona_seed_json")
    if not artifact_json:
        raise RuntimeError("Compiler pipeline did not produce persona_artifact_json.")
    artifact = PersonaArtifact.model_validate_json(artifact_json)
    row = persona_repository.publish_artifact(
        tenant_id=tenant_id,
        twin_id=twin_id,
        artifact=artifact.model_dump(mode="json"),
        publish=publish,
    )
    return {
        "artifact_id": row["id"],
        "version": artifact.version,
        "status": artifact.status,
        "quote_count": len(artifact.quote_pack),
    }


async def _run_chat(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    user_id: str,
    surface: str,
    message: str,
    conversation_id: Optional[str],
    client_context: Optional[Dict[str, Any]],
    share_token: Optional[str],
    stream: bool,
) -> AsyncGenerator[Dict[str, Any], None]:
    persona_repository = get_persona_repository()
    conversation_repository = get_conversation_repository()
    artifact_row = persona_repository.get_active_artifact(twin_id=twin_id, tenant_id=tenant_id)
    if not artifact_row:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Twin persona is not ready. Run research and compile first.",
        )

    conversation = None
    if conversation_id:
        conversation = conversation_repository.get_conversation(conversation_id=conversation_id)
        if not conversation or str(conversation.get("twin_id")) != str(twin_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    if conversation is None:
        conversation = conversation_repository.create_conversation(
            twin_id=twin_id,
            tenant_id=tenant_id,
            user_id=user_id,
            surface=surface,
            share_token=share_token,
            metadata=client_context,
            conversation_id=conversation_id or str(uuid.uuid4()),
        )

    conversation_id = conversation["id"]
    conversation_repository.add_message(
        conversation_id=conversation_id,
        twin_id=twin_id,
        tenant_id=tenant_id,
        role="user",
        content=message,
        metadata={"surface": surface},
    )

    state = {
        "tenant_id": tenant_id,
        "twin_id": twin_id,
        "conversation_id": conversation_id,
        "surface": surface,
        "client_context_json": json.dumps(client_context or {}),
    }
    await _ensure_session(
        app_name="adk_chat",
        session_id=conversation_id,
        user_id=user_id,
        state=state,
    )

    final_text = ""
    if stream:
        yield {"type": "session_started", "conversation_id": conversation_id}

    try:
        async for event in get_chat_runner().run_async(
            user_id=user_id,
            session_id=conversation_id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            if stream:
                for function_call in event.get_function_calls():
                    yield {
                        "type": "tool_call",
                        "name": function_call.name,
                        "args": function_call.args or {},
                    }
                for function_response in event.get_function_responses():
                    response_payload = function_response.response if hasattr(function_response, "response") else {}
                    yield {
                        "type": "tool_result",
                        "name": function_response.name,
                        "result": response_payload,
                    }
            text = _text_from_event(event)
            if not text:
                continue
            if getattr(event, "partial", False):
                if stream and getattr(event, "author", "") == PERSONA_RESPONDER_NAME:
                    yield {"type": "assistant_delta", "delta": text}
                continue
            if event.is_final_response() and getattr(event, "author", "") == PERSONA_RESPONDER_NAME:
                final_text = text
                if stream:
                    yield {"type": "assistant_final", "message": text}
    except Exception as exc:
        if stream:
            yield {"type": "error", "message": str(exc)}
            yield {"type": "done"}
            return
        raise

    session = await get_session_service().get_session(
        app_name="adk_chat",
        user_id=user_id,
        session_id=conversation_id,
    )
    state = session.state if session else {}
    citations = _json_list(state.get("active_citations_json"))
    conversation_repository.add_message(
        conversation_id=conversation_id,
        twin_id=twin_id,
        tenant_id=tenant_id,
        role="assistant",
        content=final_text,
        citations=citations,
        metadata={"surface": surface, "persona_version": artifact_row["artifact_json"].get("version")},
    )

    if stream:
        yield {"type": "citations", "citations": citations}
        yield {"type": "done"}
        return

    yield {
        "conversation_id": conversation_id,
        "message": final_text,
        "citations": citations,
        "persona_version": artifact_row["artifact_json"].get("version"),
        "surface": surface,
    }


async def run_chat_turn(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    user_id: str,
    surface: str,
    message: str,
    conversation_id: Optional[str] = None,
    client_context: Optional[Dict[str, Any]] = None,
    share_token: Optional[str] = None,
) -> ChatTurnResponse:
    async for payload in _run_chat(
        twin_id=twin_id,
        tenant_id=tenant_id,
        user_id=user_id,
        surface=surface,
        message=message,
        conversation_id=conversation_id,
        client_context=client_context,
        share_token=share_token,
        stream=False,
    ):
        return ChatTurnResponse(**payload)
    raise RuntimeError("Chat runtime returned no payload.")


async def stream_chat_turn(
    *,
    twin_id: str,
    tenant_id: Optional[str],
    user_id: str,
    surface: str,
    message: str,
    conversation_id: Optional[str] = None,
    client_context: Optional[Dict[str, Any]] = None,
    share_token: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    async for payload in _run_chat(
        twin_id=twin_id,
        tenant_id=tenant_id,
        user_id=user_id,
        surface=surface,
        message=message,
        conversation_id=conversation_id,
        client_context=client_context,
        share_token=share_token,
        stream=True,
    ):
        yield payload
