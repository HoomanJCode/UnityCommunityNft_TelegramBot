"""Tests for admin authentication (login + bearer-token gate)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.api.admin as admin_mod
from backend.db.models import Base

# Importing `app` registers the admin blueprint.
from backend.main import app


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(admin_mod, "SessionLocal", Session)

    # The in-memory login rate limiter is module-global; reset it so one
    # test's login attempt never throttles the next test.
    monkeypatch.setattr(admin_mod, "_last_login_attempt", 0.0)

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_routes_open_when_auth_disabled(client, monkeypatch):
    """With no ADMIN_PASSWORD set, admin routes stay open (dev mode)."""
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    r = client.get("/admin/badge-types")
    assert r.status_code == 200


def test_auth_status_probe(client, monkeypatch):
    """The boot probe reports auth state and is never blocked by the gate."""
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert client.get("/admin/auth/status").get_json() == {"enabled": False}

    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    r = client.get("/admin/auth/status")
    assert r.status_code == 200
    assert r.get_json() == {"enabled": True}


def test_probe_does_not_throttle_login(client, monkeypatch):
    """Probing /auth/status must not consume the login rate limiter."""
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    client.get("/admin/auth/status")
    # The very next login (immediately after the probe) must NOT be 429.
    r = client.post("/admin/login", json={"password": "s3cret"})
    assert r.status_code == 200


def test_login_rejects_when_auth_disabled(client, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    r = client.post("/admin/login", json={"password": "anything"})
    assert r.status_code == 403


def test_routes_require_token_when_auth_enabled(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    r = client.get("/admin/badge-types")
    assert r.status_code == 401


def test_login_wrong_password(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    r = client.post("/admin/login", json={"password": "nope"})
    assert r.status_code == 401


def test_login_success_and_token_works(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    r = client.post("/admin/login", json={"password": "s3cret"})
    assert r.status_code == 200
    token = r.get_json()["token"]

    # The token unlocks admin routes.
    r = client.get(
        "/admin/badge-types", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200

    # A garbage token is rejected.
    r = client.get(
        "/admin/badge-types", headers={"Authorization": "Bearer garbage"}
    )
    assert r.status_code == 401


def test_login_rate_limited(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    client.post("/admin/login", json={"password": "wrong"})
    # Immediately after, a second attempt is throttled.
    r = client.post("/admin/login", json={"password": "s3cret"})
    assert r.status_code == 429
