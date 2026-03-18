"""Supabase-backed ADK session service."""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from google.adk.events import Event
from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import GetSessionConfig, ListSessionsResponse

from adk_core.repositories.session_repository import SessionRepository


class AdkDatabaseSessionService(BaseSessionService):
    """Stores ADK Session objects in the authoritative adk_sessions table."""

    def __init__(self, repository: Optional[SessionRepository] = None):
        super().__init__()
        self._repository = repository or SessionRepository()

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session = Session(
            id=session_id or str(uuid.uuid4()),
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=time.time(),
        )
        self._repository.save(
            session=session,
            tenant_id=session.state.get("tenant_id"),
            twin_id=session.state.get("twin_id"),
        )
        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[GetSessionConfig] = None,
    ) -> Optional[Session]:
        del config
        return self._repository.get(app_name=app_name, user_id=user_id, session_id=session_id)

    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: Optional[str] = None,
    ) -> ListSessionsResponse:
        return ListSessionsResponse(sessions=self._repository.list(app_name=app_name, user_id=user_id))

    async def delete_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        self._repository.delete(app_name=app_name, user_id=user_id, session_id=session_id)

    async def append_event(self, session: Session, event: Event) -> Event:
        event = await super().append_event(session, event)
        session.last_update_time = time.time()
        self._repository.save(
            session=session,
            tenant_id=session.state.get("tenant_id"),
            twin_id=session.state.get("twin_id"),
        )
        return event
