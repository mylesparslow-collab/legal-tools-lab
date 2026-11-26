"""Server-side sessions for the local web UI.

A demo stand-in for the firm's single sign-on. The browser holds an opaque
random token in a cookie; the server keeps the mapping from token to person.
The person a query runs as is read from that mapping and from nowhere else,
so it is not something a user can edit in a URL.

What a pilot would replace: ``SessionStore.issue`` is called today after a
demo user picker. In a real deployment it would be called only after the
firm's identity provider has confirmed who the person is. Everything
downstream (cookie, lookup, expiry, sign-out) can stay.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
import time


class SessionStore:
    def __init__(self, ttl_seconds: int = 8 * 3600, clock=time.time):
        self.ttl = ttl_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._sessions: dict = {}   # sha256(token) -> (person_id, expires_at)

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(self, person_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[self._key(token)] = (person_id, self.clock() + self.ttl)
        return token

    def resolve(self, token: str | None):
        """The person a token belongs to, or None if unknown or expired."""
        if not token:
            return None
        key = self._key(token)
        with self._lock:
            entry = self._sessions.get(key)
            if entry is None:
                return None
            if entry[1] < self.clock():
                del self._sessions[key]
                return None
            return entry[0]

    def revoke(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(self._key(token), None)
