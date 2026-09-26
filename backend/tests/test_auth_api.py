"""Tests for the authentication API: registration, login, session lookup,
logout, and the forgot/reset-password flow.

Covers exactly the failure modes Task 3 called out as bugs: login must
reject an unregistered email, must actually verify the password (not just
"email exists"), duplicate registration must be rejected, and a reset token
must flip which password is accepted.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from auth.store import PASSWORD_RESET_STORE, SESSION_STORE, USER_STORE

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def clean_auth_stores():
    """Each test starts with an empty user/session/reset-token store - these
    are module-level singletons shared across the whole test session."""
    USER_STORE.clear()
    SESSION_STORE.clear()
    PASSWORD_RESET_STORE.clear()
    yield
    USER_STORE.clear()
    SESSION_STORE.clear()
    PASSWORD_RESET_STORE.clear()


def _register(email="test@example.com", password="Password123", **overrides):
    body = {
        "name": "Test User",
        "position": "Dispatcher",
        "company": "Test Logistics",
        "email": email,
        "password": password,
    }
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


# ============================================================== registration

def test_register_creates_account_and_returns_token_and_public_user():
    res = _register()
    assert res.status_code == 200
    data = res.json()
    assert data["token"]
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"
    assert data["user"]["position"] == "Dispatcher"
    assert data["user"]["company"] == "Test Logistics"
    # Never echo password or its hash back to the client.
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_register_normalizes_email_case_and_whitespace():
    res = _register(email="  Test@Example.COM  ")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "test@example.com"


def test_register_rejects_duplicate_email():
    first = _register()
    assert first.status_code == 200

    second = _register(name="Someone Else")
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_register_rejects_duplicate_email_case_insensitively():
    assert _register(email="dup@example.com").status_code == 200
    second = _register(email="DUP@example.com", name="Someone Else")
    assert second.status_code == 409


def test_register_rejects_short_password():
    res = _register(password="short")
    assert res.status_code == 400
    assert "8 characters" in res.json()["detail"]


def test_register_rejects_invalid_email_format():
    res = _register(email="not-an-email")
    assert res.status_code == 400
    assert "valid email" in res.json()["detail"]


@pytest.mark.parametrize("field", ["name", "position", "company"])
def test_register_rejects_blank_required_fields(field):
    res = _register(**{field: "   "})
    assert res.status_code == 400


# ======================================================================= login

def test_login_rejects_unregistered_email():
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Password123"})
    assert res.status_code == 401
    assert "No account found" in res.json()["detail"]


def test_login_rejects_wrong_password():
    _register()
    res = client.post("/api/auth/login", json={"email": "test@example.com", "password": "WrongPassword"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Incorrect email or password."


def test_login_succeeds_with_correct_credentials():
    _register()
    res = client.post("/api/auth/login", json={"email": "test@example.com", "password": "Password123"})
    assert res.status_code == 200
    data = res.json()
    assert data["token"]
    assert data["user"]["email"] == "test@example.com"


def test_login_does_not_accept_arbitrary_password_for_registered_email():
    """Regression guard for the original bug: login must not be
    `if email exists: success`. Two different bad passwords both fail."""
    _register()
    for bad_password in ("WrongPassword1", "Password124", "password123"):
        res = client.post("/api/auth/login", json={"email": "test@example.com", "password": bad_password})
        assert res.status_code == 401, bad_password


def test_login_is_case_insensitive_on_email_but_not_on_password():
    _register()
    res = client.post("/api/auth/login", json={"email": "TEST@EXAMPLE.COM", "password": "Password123"})
    assert res.status_code == 200

    res_wrong_case_password = client.post(
        "/api/auth/login", json={"email": "test@example.com", "password": "password123"}
    )
    assert res_wrong_case_password.status_code == 401


def test_login_rejects_short_password_before_even_checking_the_account():
    res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "short"})
    assert res.status_code == 400


# ================================================================ session/me

def test_me_returns_current_user_for_a_valid_token():
    token = _register().json()["token"]
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "test@example.com"


def test_me_rejects_missing_token():
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_rejects_garbage_token():
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_logout_revokes_the_session_token():
    token = _register().json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_logout.status_code == 401


# ================================================================= forgot/reset

def test_forgot_password_returns_neutral_message_for_unknown_email():
    res = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 200
    assert "If an account exists" in res.json()["message"]
    # Nothing to reset for an email with no account - no token to expose.
    assert "dev_reset_token" not in res.json()


def test_forgot_password_returns_same_neutral_message_for_known_email():
    _register()
    res = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    assert res.status_code == 200
    assert "If an account exists" in res.json()["message"]


def test_forgot_password_dev_token_is_absent_in_production_mode(monkeypatch):
    _register()
    monkeypatch.setattr(main_module, "IS_PRODUCTION", True)
    res = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    assert res.status_code == 200
    assert "dev_reset_token" not in res.json()


def test_reset_password_flow_old_password_rejected_new_password_accepted():
    _register(password="Password123")

    forgot_res = client.post("/api/auth/forgot-password", json={"email": "test@example.com"})
    token = forgot_res.json()["dev_reset_token"]

    reset_res = client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "NewPassword456"}
    )
    assert reset_res.status_code == 200

    old_login = client.post("/api/auth/login", json={"email": "test@example.com", "password": "Password123"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": "test@example.com", "password": "NewPassword456"})
    assert new_login.status_code == 200


def test_reset_password_token_is_single_use():
    _register()
    token = client.post("/api/auth/forgot-password", json={"email": "test@example.com"}).json()["dev_reset_token"]

    first = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassword456"})
    assert first.status_code == 200

    second = client.post("/api/auth/reset-password", json={"token": token, "new_password": "AnotherPassword789"})
    assert second.status_code == 400


def test_reset_password_rejects_unknown_token():
    res = client.post(
        "/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "NewPassword456"}
    )
    assert res.status_code == 400


def test_reset_password_rejects_short_new_password():
    _register()
    token = client.post("/api/auth/forgot-password", json={"email": "test@example.com"}).json()["dev_reset_token"]
    res = client.post("/api/auth/reset-password", json={"token": token, "new_password": "short"})
    assert res.status_code == 400
