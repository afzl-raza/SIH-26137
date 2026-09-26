"""Tests for auth/security.py's password hashing and token generation, in
isolation from the API layer."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth.security import generate_token, hash_password, verify_password


def test_hash_password_never_stores_the_plaintext():
    stored = hash_password("Password123")
    assert "Password123" not in stored


def test_hash_password_is_salted_so_identical_passwords_hash_differently():
    a = hash_password("Password123")
    b = hash_password("Password123")
    assert a != b


def test_verify_password_accepts_the_correct_password():
    stored = hash_password("Password123")
    assert verify_password("Password123", stored) is True


def test_verify_password_rejects_a_wrong_password():
    stored = hash_password("Password123")
    assert verify_password("WrongPassword", stored) is False


def test_verify_password_is_case_sensitive():
    stored = hash_password("Password123")
    assert verify_password("password123", stored) is False


def test_verify_password_handles_malformed_stored_hash_without_raising():
    assert verify_password("Password123", "not-a-real-hash") is False
    assert verify_password("Password123", "") is False
    assert verify_password("Password123", None) is False


def test_generate_token_returns_distinct_unguessable_values():
    tokens = {generate_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)
