"""Password hashing/verification and opaque token generation.

Uses PBKDF2-HMAC-SHA256 from the standard library rather than adding a new
dependency (bcrypt/passlib) for a prototype-scale user store - the same
construction Django's default password hasher uses, just without the library
wrapper: a per-user random salt plus a work factor high enough to make
brute-forcing an exfiltrated (hash, salt) pair impractical, and a
constant-time comparison so verification can't leak timing information about
how much of the hash matched.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Returns a self-describing hash string: algorithm$iterations$salt$hash."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = _derive(password, salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Recomputes the hash with the stored salt/iterations and compares in
    constant time. Never raises on malformed input - returns False instead,
    since a corrupt stored hash must never be treated as "any password
    matches"."""
    try:
        algorithm, iterations_str, salt, expected = stored.split("$")
        iterations = int(iterations_str)
    except (ValueError, AttributeError):
        return False
    if algorithm != _ALGORITHM:
        return False
    candidate = _derive(password, salt, iterations)
    return hmac.compare_digest(candidate, expected)


def _derive(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()


def generate_token() -> str:
    """Opaque, unguessable token used for both session and password-reset
    tokens - 32 random bytes, URL-safe encoded."""
    return secrets.token_urlsafe(32)
