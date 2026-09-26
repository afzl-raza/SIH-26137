"""In-memory user, session, and password-reset-token stores.

Scope: same as realdata/scenario_store.py - an in-process store for a
single-process prototype deployment, not a database. Thread-safe via a lock
because FastAPI runs sync `def` endpoints in a worker threadpool. Restarting
the backend process drops every account, session and reset token; that is
an accepted limitation of this prototype, not something masked from callers.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .security import generate_token, hash_password

# 30 minutes: long enough to act on a reset link, short enough that a stale
# unused token stops being useful quickly.
RESET_TOKEN_TTL_SECONDS = 30 * 60
# 7 days: keeps a demo session alive across a normal workday without needing
# a refresh-token dance for a single-process prototype.
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60


class EmailAlreadyRegisteredError(Exception):
    """Raised by UserStore.create() when the normalized email is taken."""


@dataclass
class User:
    id: str
    name: str
    position: str
    company: str
    email: str  # normalized: trimmed + lowercased
    password_hash: str
    created_at: float
    updated_at: float

    def public(self) -> dict:
        """Fields safe to send to the client - password_hash never leaves
        this module."""
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "company": self.company,
            "email": self.email,
        }


class UserStore:
    """Thread-safe in-memory user directory, keyed by normalized email."""

    def __init__(self):
        self._lock = threading.RLock()
        self._by_email: Dict[str, User] = {}
        self._by_id: Dict[str, User] = {}
        self._next_id = 1

    @staticmethod
    def normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    def create(self, *, name: str, position: str, company: str, email: str, password: str) -> User:
        normalized = self.normalize_email(email)
        with self._lock:
            if normalized in self._by_email:
                raise EmailAlreadyRegisteredError(normalized)
            now = time.time()
            user = User(
                id=str(self._next_id),
                name=name.strip(),
                position=position,
                company=company.strip(),
                email=normalized,
                password_hash=hash_password(password),
                created_at=now,
                updated_at=now,
            )
            self._next_id += 1
            self._by_email[normalized] = user
            self._by_id[user.id] = user
            return user

    def get_by_email(self, email: str) -> Optional[User]:
        with self._lock:
            return self._by_email.get(self.normalize_email(email))

    def get_by_id(self, user_id: str) -> Optional[User]:
        with self._lock:
            return self._by_id.get(user_id)

    def set_password(self, user_id: str, password: str) -> None:
        with self._lock:
            user = self._by_id.get(user_id)
            if user is None:
                return
            user.password_hash = hash_password(password)
            user.updated_at = time.time()

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_id)

    def clear(self) -> None:
        """Test-only: reset the store between test cases."""
        with self._lock:
            self._by_email.clear()
            self._by_id.clear()
            self._next_id = 1


@dataclass
class Session:
    token: str
    user_id: str
    created_at: float
    expires_at: float


class SessionStore:
    """Maps an opaque bearer token to a user id, with a sliding TTL."""

    def __init__(self, ttl_seconds: float = SESSION_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._sessions: Dict[str, Session] = {}

    def create(self, user_id: str) -> Session:
        now = time.time()
        session = Session(
            token=generate_token(), user_id=user_id, created_at=now, expires_at=now + self._ttl
        )
        with self._lock:
            self._sessions[session.token] = session
        return session

    def get_user_id(self, token: str) -> Optional[str]:
        if not token:
            return None
        now = time.time()
        with self._lock:
            session = self._sessions.get(token)
            if session is None:
                return None
            if session.expires_at < now:
                del self._sessions[token]
                return None
            return session.user_id

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        """Test-only: reset the store between test cases."""
        with self._lock:
            self._sessions.clear()


@dataclass
class ResetToken:
    token: str
    user_id: str
    created_at: float
    expires_at: float
    used: bool = False


class PasswordResetStore:
    """Maps a one-time reset token to the user it was issued for.

    No email-delivery infrastructure exists in this repository (there is no
    SMTP client or provider anywhere in backend/), so nothing here sends an
    email - see main.py's /api/auth/forgot-password handler for how the token
    is surfaced in development only.
    """

    def __init__(self, ttl_seconds: float = RESET_TOKEN_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._tokens: Dict[str, ResetToken] = {}

    def create(self, user_id: str) -> ResetToken:
        now = time.time()
        record = ResetToken(
            token=generate_token(), user_id=user_id, created_at=now, expires_at=now + self._ttl
        )
        with self._lock:
            self._tokens[record.token] = record
        return record

    def consume(self, token: str) -> Optional[str]:
        """Validates and immediately invalidates a reset token, returning the
        user_id it was issued for, or None if it's unknown, expired, or
        already used."""
        if not token:
            return None
        now = time.time()
        with self._lock:
            record = self._tokens.get(token)
            if record is None or record.used or record.expires_at < now:
                return None
            record.used = True
            return record.user_id

    def clear(self) -> None:
        """Test-only: reset the store between test cases."""
        with self._lock:
            self._tokens.clear()


# Module-level stores used by the API layer.
USER_STORE = UserStore()
SESSION_STORE = SessionStore()
PASSWORD_RESET_STORE = PasswordResetStore()
