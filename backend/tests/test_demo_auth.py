"""Tests for DEMO_AUTH mode: the hackathon/demo login path that accepts any
non-empty email + non-empty password, with no account or password match
required. DEMO_AUTH defaults to False (see main.py), so these tests flip it
on via monkeypatch - test_auth_api.py covers the real-auth behavior that
runs when it's off, and must keep passing unchanged regardless of this file.
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
def demo_auth_enabled(monkeypatch):
    monkeypatch.setattr(main_module, "DEMO_AUTH", True)
    USER_STORE.clear()
    SESSION_STORE.clear()
    PASSWORD_RESET_STORE.clear()
    yield
    USER_STORE.clear()
    SESSION_STORE.clear()
    PASSWORD_RESET_STORE.clear()


def test_demo_login_succeeds_for_any_email_and_password():
    res = client.post(
        "/api/auth/login", json={"email": "anything@example.com", "password": "123"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["token"]
    assert data["user"]["email"] == "anything@example.com"


def test_demo_login_succeeds_with_a_different_short_password():
    res = client.post("/api/auth/login", json={"email": "demo@test.com", "password": "hello"})
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "demo@test.com"


def test_demo_login_does_not_require_prior_registration():
    # No _register() call anywhere before this - the whole point of demo
    # mode is that no account needs to exist first.
    res = client.post("/api/auth/login", json={"email": "brand-new@example.com", "password": "x"})
    assert res.status_code == 200


def test_demo_login_ignores_password_mismatch_on_repeat_login():
    first = client.post("/api/auth/login", json={"email": "repeat@example.com", "password": "first-password"})
    assert first.status_code == 200

    second = client.post(
        "/api/auth/login", json={"email": "repeat@example.com", "password": "totally-different"}
    )
    assert second.status_code == 200
    # Same underlying account both times, not two different users.
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_demo_login_rejects_empty_password():
    res = client.post("/api/auth/login", json={"email": "someone@example.com", "password": ""})
    assert res.status_code == 400


def test_demo_login_rejects_invalid_email_format():
    res = client.post("/api/auth/login", json={"email": "not-an-email", "password": "x"})
    assert res.status_code == 400


def test_demo_register_never_conflicts_on_duplicate_email():
    body = {
        "name": "Test User",
        "position": "Dispatcher",
        "company": "Test Logistics",
        "email": "dup-demo@example.com",
        "password": "123",
    }
    first = client.post("/api/auth/register", json=body)
    assert first.status_code == 200

    second = client.post("/api/auth/register", json={**body, "password": "456"})
    assert second.status_code == 200


def test_demo_register_accepts_short_password():
    res = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "position": "Dispatcher",
            "company": "Test Logistics",
            "email": "shortpw@example.com",
            "password": "ab",
        },
    )
    assert res.status_code == 200


def test_demo_session_persists_across_me_and_logout_still_works():
    token = client.post(
        "/api/auth/login", json={"email": "session@example.com", "password": "123"}
    ).json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "session@example.com"

    logout_res = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200

    after_logout = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_logout.status_code == 401


def test_health_reports_demo_auth_state():
    assert client.get("/api/health").json()["demo_auth"] is True
