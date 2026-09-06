# backend/sessions.py
"""Keyed, TTL'd session registry — replaces the old module-level _active_session_id global.

Each frontend tab generates its own stream_id and registers it here, receiving a signed
token that gates its SSE subscription. Webhook routing resolves conversation_id purely
from the incoming request (params.stream_id, falling back to ElevenLabs' own
conversation_id) — there is no shared mutable state a second driver's request can
overwrite, so two concurrent sessions can never cross-contaminate.
"""
import secrets
from dataclasses import dataclass
from time import monotonic

from backend.config import SESSION_TTL_SECONDS


class CapacityError(Exception):
    pass


@dataclass
class Session:
    stream_id: str
    created_at: float
    token: str


class SessionRegistry:
    def __init__(self, ttl: float = SESSION_TTL_SECONDS, max_size: int = 10_000):
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl
        self._max = max_size

    def register(self, stream_id: str) -> str:
        self._sweep()
        if stream_id not in self._sessions and len(self._sessions) >= self._max:
            raise CapacityError("session registry full")
        token = secrets.token_urlsafe(32)
        self._sessions[stream_id] = Session(stream_id, monotonic(), token)
        return token

    def verify(self, stream_id: str, token: str) -> bool:
        session = self._sessions.get(stream_id)
        if session is None:
            return False
        if monotonic() - session.created_at > self._ttl:
            self._sessions.pop(stream_id, None)
            return False
        return secrets.compare_digest(session.token, token)

    def is_registered(self, stream_id: str) -> bool:
        session = self._sessions.get(stream_id)
        if session is None:
            return False
        if monotonic() - session.created_at > self._ttl:
            self._sessions.pop(stream_id, None)
            return False
        return True

    def _sweep(self) -> None:
        now = monotonic()
        expired = [k for k, v in self._sessions.items() if now - v.created_at > self._ttl]
        for k in expired:
            self._sessions.pop(k, None)


registry = SessionRegistry()
