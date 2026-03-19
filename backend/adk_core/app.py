"""Root assembly for ADK runners and repositories."""

from __future__ import annotations

from functools import lru_cache

from google.adk.runners import Runner

from adk_core.agents import build_chat_root_agent, build_compiler_pipeline_agent, build_research_pipeline_agent
from adk_core.modeling import DEFAULT_CEREBRAS_RESEARCH_MODEL, resolve_model_for_env
from adk_core.repositories import ConversationRepository, PersonaRepository, ResearchRepository, SessionRepository
from adk_core.services import AdkDatabaseSessionService


@lru_cache(maxsize=1)
def get_session_repository() -> SessionRepository:
    return SessionRepository()


@lru_cache(maxsize=1)
def get_session_service() -> AdkDatabaseSessionService:
    return AdkDatabaseSessionService(repository=get_session_repository())


@lru_cache(maxsize=1)
def get_research_repository() -> ResearchRepository:
    return ResearchRepository()


@lru_cache(maxsize=1)
def get_persona_repository() -> PersonaRepository:
    return PersonaRepository()


@lru_cache(maxsize=1)
def get_conversation_repository() -> ConversationRepository:
    return ConversationRepository()


@lru_cache(maxsize=1)
def get_chat_runner() -> Runner:
    model = resolve_model_for_env("ADK_CHAT_MODEL")
    return Runner(
        app_name="adk_chat",
        agent=build_chat_root_agent(model=model),
        session_service=get_session_service(),
    )


@lru_cache(maxsize=1)
def get_research_runner() -> Runner:
    model = resolve_model_for_env(
        "ADK_RESEARCH_MODEL",
        fallback_model=DEFAULT_CEREBRAS_RESEARCH_MODEL,
        fallback_provider="cerebras",
    )
    return Runner(
        app_name="adk_research",
        agent=build_research_pipeline_agent(model=model),
        session_service=get_session_service(),
    )


@lru_cache(maxsize=1)
def get_compiler_runner() -> Runner:
    model = resolve_model_for_env("ADK_COMPILER_MODEL")
    return Runner(
        app_name="adk_compiler",
        agent=build_compiler_pipeline_agent(model=model),
        session_service=get_session_service(),
    )
