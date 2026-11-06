from threading import Lock
from uuid import UUID

from .schemas import ResearchSession


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, ResearchSession] = {}
        self._lock = Lock()

    def create(self, session: ResearchSession) -> ResearchSession:
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: UUID) -> ResearchSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def update(self, session: ResearchSession) -> ResearchSession:
        with self._lock:
            if session.session_id not in self._sessions:
                raise KeyError(f"Research session {session.session_id} does not exist")
            self._sessions[session.session_id] = session
        return session


session_store = SessionStore()
