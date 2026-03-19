"""Execution helpers and event translation for the ADK runtime."""

from __future__ import annotations

import json
import re
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


def _coerce_json_text(raw: Any) -> str:
    if raw is None:
        raise ValueError("Expected JSON payload, got None.")
    if isinstance(raw, (dict, list)):
        return json.dumps(raw)
    text = str(raw).strip()
    if not text:
        raise ValueError("Expected JSON payload, got blank text.")

    candidates: List[str] = []
    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

    start_object = text.find("{")
    end_object = text.rfind("}")
    if start_object != -1 and end_object != -1 and end_object > start_object:
        candidates.append(text[start_object : end_object + 1].strip())

    start_array = text.find("[")
    end_array = text.rfind("]")
    if start_array != -1 and end_array != -1 and end_array > start_array:
        candidates.append(text[start_array : end_array + 1].strip())

    candidates.append(text)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        return json.dumps(parsed)
    raise ValueError("Unable to extract valid JSON from model output.")


def _stable_session_id(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, ":".join(parts)))


def _persona_prompt_block(artifact: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "identity_frame": artifact.get("identity_frame") or {},
            "thinking_style": artifact.get("thinking_style") or {},
            "values_and_decision_heuristics": artifact.get("values_and_decision_heuristics") or [],
            "communication_rules": artifact.get("communication_rules") or [],
            "voice_dna": artifact.get("voice_dna") or {},
        }
    )


def _coerce_json_obj(raw: Any, default: Any) -> Any:
    try:
        return json.loads(_coerce_json_text(raw))
    except Exception:
        return default


def _confidence_value(raw: Any) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or "").strip().lower()
    if text in {"high", "strong"}:
        return 0.85
    if text in {"medium", "moderate"}:
        return 0.6
    if text in {"low", "weak"}:
        return 0.35
    try:
        return float(text)
    except Exception:
        return 0.0


def _normalize_claims(rows: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows or [], start=1):
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        normalized.append(
            {
                "claim_id": str(row.get("claim_id") or f"claim-{idx}"),
                "text": text,
                "claim_type": str(row.get("claim_type") or "other"),
                "confidence": _confidence_value(row.get("confidence")),
                "source_ids": [str(item) for item in (row.get("source_ids") or []) if item],
            }
        )
    return normalized


def _normalize_timeline(rows: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        date_or_range = str(row.get("date_or_range") or "").strip()
        event = str(row.get("event") or "").strip()
        if not date_or_range or not event:
            continue
        normalized.append(
            {
                "date_or_range": date_or_range,
                "event": event,
                "confidence": _confidence_value(row.get("confidence")),
                "source_ids": [str(item) for item in (row.get("source_ids") or []) if item],
            }
        )
    return normalized


def _normalize_quotes(rows: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or row.get("quote_text") or "").strip()
        source_id = str(row.get("source_id") or "").strip()
        if not quote or not source_id:
            continue
        normalized.append(
            {
                "quote": quote,
                "source_id": source_id,
                "confidence": _confidence_value(row.get("confidence")),
                "speaker": row.get("speaker"),
                "context": str(row.get("context") or "").strip(),
            }
        )
    return normalized


def _build_research_artifact_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    gathered = _coerce_json_obj(state.get("gathered_research_json"), {})
    identity = _coerce_json_obj(state.get("identity_analysis_json"), {})
    evidence = _coerce_json_obj(state.get("evidence_analysis_json"), {})
    source_registry = gathered.get("source_registry") or []
    claims = _normalize_claims(evidence.get("extracted_claims"))
    timeline = _normalize_timeline(evidence.get("timeline"))
    quotes = _normalize_quotes(evidence.get("quote_candidates"))
    if not quotes:
        quotes = _normalize_quotes(gathered.get("verified_quote_candidates"))

    subject_name = str(gathered.get("subject_name") or state.get("subject_name") or "").strip()
    subject_identity = {
        "canonical_name": identity.get("canonical_name") or subject_name,
        "public_roles": identity.get("public_roles") or [],
        "organizations": identity.get("organizations") or [],
        "locations": identity.get("locations") or [],
        "expertise_topics": identity.get("expertise_topics") or [],
        "short_bio": identity.get("short_bio") or str(state.get("research_gather_summary") or "").strip(),
        "evidence_notes": identity.get("evidence_notes") or "",
    }
    return {
        "subject_identity": subject_identity,
        "source_registry": source_registry,
        "extracted_claims": claims,
        "timeline": timeline,
        "verified_quote_candidates": quotes,
        "synthesis_summary": subject_identity["short_bio"] or f"Research summary for {subject_name}".strip(),
        "compile_metadata": {
            "generated_by": "adk_research_pipeline_fallback",
            "source_count": len(source_registry),
            "quote_count": len(quotes),
            "gather_stats": gathered.get("gather_stats") or {},
        },
    }


def _normalize_research_artifact_payload(
    payload: Dict[str, Any],
    *,
    fallback: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback
    subject_identity = payload.get("subject_identity")
    if not isinstance(subject_identity, dict):
        subject_identity = fallback.get("subject_identity") or {}
    source_registry = payload.get("source_registry")
    if not isinstance(source_registry, list):
        source_registry = fallback.get("source_registry") or []
    synthesis_summary = str(
        payload.get("synthesis_summary")
        or fallback.get("synthesis_summary")
        or ""
    ).strip()
    compile_metadata = payload.get("compile_metadata")
    if not isinstance(compile_metadata, dict):
        compile_metadata = fallback.get("compile_metadata") or {}
    return {
        "subject_identity": subject_identity,
        "source_registry": source_registry,
        "extracted_claims": _normalize_claims(
            payload.get("extracted_claims") or fallback.get("extracted_claims")
        ),
        "timeline": _normalize_timeline(payload.get("timeline") or fallback.get("timeline")),
        "verified_quote_candidates": _normalize_quotes(
            payload.get("verified_quote_candidates") or fallback.get("verified_quote_candidates")
        ),
        "synthesis_summary": synthesis_summary,
        "compile_metadata": compile_metadata,
    }


def _normalize_persona_artifact_payload(
    payload: Dict[str, Any],
    *,
    fallback: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return fallback
    allowed_keys = set(PersonaArtifact.model_fields.keys())
    normalized = dict(fallback)
    normalized.update({key: value for key, value in payload.items() if key in allowed_keys})
    return normalized


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
        fallback_payload = _build_research_artifact_payload(session.state)
        artifact_payload = _normalize_research_artifact_payload(
            _coerce_json_obj(session.state.get("research_artifact_json"), {}),
            fallback=fallback_payload,
        )
        artifact = ResearchArtifact.model_validate(artifact_payload)
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
    session_id = _stable_session_id(run_id, twin_id, "compile")
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
    seed_payload = _coerce_json_obj(session.state.get("persona_seed_json"), {})
    artifact_payload = _normalize_persona_artifact_payload(
        _coerce_json_obj(session.state.get("persona_artifact_json"), seed_payload),
        fallback=seed_payload,
    )
    if not artifact_payload:
        raise RuntimeError("Compiler pipeline did not produce persona_artifact_json.")
    artifact = PersonaArtifact.model_validate(artifact_payload)
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
        "persona_artifact_json": json.dumps(artifact_row.get("artifact_json") or {}),
        "persona_prompt_block": _persona_prompt_block(artifact_row.get("artifact_json") or {}),
        "quote_pack_json": json.dumps((artifact_row.get("artifact_json") or {}).get("quote_pack") or []),
        "recent_conversation_json": "[]",
        "fact_context_json": "[]",
        "quote_context_json": "[]",
        "fact_citations_json": "[]",
        "quote_citations_json": "[]",
        "active_citations_json": "[]",
        "coordinator_brief": "{}",
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
