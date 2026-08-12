"""Integration tests for the admin API (Flask test client)."""

import io

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

    # Point the admin module's SessionLocal at the test DB.
    monkeypatch.setattr(admin_mod, "SessionLocal", Session)

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _create_badge(client, name="VIP", soulbound=False):
    return client.post(
        "/admin/badge-types", json={"name": name, "is_soulbound": soulbound}
    )


def test_badge_type_crud(client):
    r = _create_badge(client)
    assert r.status_code == 201
    b_id = r.get_json()["id"]
    assert r.get_json()["is_soulbound"] is False

    r = client.get("/admin/badge-types")
    assert r.status_code == 200
    assert len(r.get_json()) == 1

    r = client.put(f"/admin/badge-types/{b_id}", json={"description": "premium"})
    assert r.status_code == 200
    assert r.get_json()["description"] == "premium"

    r = client.delete(f"/admin/badge-types/{b_id}")
    assert r.status_code == 200
    assert client.get("/admin/badge-types").get_json() == []


def test_create_badge_requires_name(client):
    assert client.post("/admin/badge-types", json={}).status_code == 400


def test_event_crud(client):
    badge_id = _create_badge(client).get_json()["id"]

    r = client.post("/admin/events", json={"name": "Meetup"})
    assert r.status_code == 201
    e_id = r.get_json()["id"]

    r = client.get("/admin/events")
    assert len(r.get_json()) == 1

    r = client.put(f"/admin/events/{e_id}", json={"badge_type_id": badge_id})
    assert r.get_json()["badge_type_id"] == badge_id

    assert client.delete(f"/admin/events/{e_id}").status_code == 200


def test_event_rejects_unknown_badge_type(client):
    r = client.post("/admin/events", json={"name": "X", "badge_type_id": 999})
    assert r.status_code == 404


def test_create_assignments_json(client, monkeypatch):
    from backend.db.models import User

    _create_badge(client)
    # Seed two users directly into the (monkeypatched) session.
    from backend.api.admin import SessionLocal

    with SessionLocal() as db:
        db.add(User(telegram_id=1, phone="79991112233"))
        db.add(User(telegram_id=2, phone="79995556677", wallet_address="EQD..."))
        db.commit()

    r = client.post(
        "/admin/assignments",
        json={"badge_type_id": 1, "phones": ["79991112233", "79995556677"]},
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["created"] == 1
    assert body["needs_wallet"] == 1


def test_create_assignments_csv(client):
    from backend.db.models import User
    from backend.api.admin import SessionLocal

    _create_badge(client)
    with SessionLocal() as db:
        db.add(User(telegram_id=1, phone="79991112233", wallet_address="EQD..."))
        db.commit()

    csv_data = io.BytesIO(b"phone\n79991112233\n")
    r = client.post(
        "/admin/assignments/upload",
        data={"badge_type_id": 1, "file": (csv_data, "phones.csv")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    assert r.get_json()["created"] == 1


def test_assignment_status_transition(client):
    from backend.db.models import Assignment
    from backend.api.admin import SessionLocal

    _create_badge(client)
    with SessionLocal() as db:
        a = Assignment(badge_type_id=1, user_id=1, status="pending")
        db.add(a)
        db.commit()
        a_id = a.id

    r = client.post(f"/admin/assignments/{a_id}/status", json={"status": "queued"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "queued"

    # Invalid transition -> 409
    r = client.post(f"/admin/assignments/{a_id}/status", json={"status": "minted"})
    assert r.status_code == 409
