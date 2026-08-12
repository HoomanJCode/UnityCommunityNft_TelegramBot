"""Integration tests for the Mini App API."""

import hashlib
import hmac
import json
from urllib.parse import urlencode

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.api.mini_app as mini_app_mod
from backend.db.models import Assignment, BadgeType, Base, User

from backend.main import app

BOT_TOKEN = "123456:ABC-DEF"


def _make_init_data(fields: dict) -> str:
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    sig = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode({**fields, "hash": sig})


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    monkeypatch.setattr(mini_app_mod, "SessionLocal", Session)
    monkeypatch.setattr(mini_app_mod, "_bot_token", lambda: BOT_TOKEN)

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _init_data(user_id: int = 42) -> str:
    return _make_init_data(
        {"auth_date": "1700000000", "user": json.dumps({"id": user_id})}
    )


def test_link_wallet(client, monkeypatch):
    from backend.api.mini_app import SessionLocal

    r = client.post(
        "/miniapp/wallet",
        json={"init_data": _init_data(42), "wallet_address": "EQD..."},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["wallet_address"] == "EQD..."
    assert body["telegram_id"] == 42

    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == 42).first()
        assert user.wallet_address == "EQD..."
        assert user.wallet_connected_at is not None


def test_link_wallet_rejects_invalid_init_data(client):
    r = client.post(
        "/miniapp/wallet",
        json={"init_data": "auth_date=1", "wallet_address": "EQD..."},
    )
    assert r.status_code == 401


def test_link_wallet_requires_wallet(client):
    r = client.post("/miniapp/wallet", json={"init_data": _init_data(42)})
    assert r.status_code == 400


def test_list_badges_returns_minted(client):
    from backend.api.mini_app import SessionLocal

    with SessionLocal() as db:
        user = User(telegram_id=42, wallet_address="EQD...")
        db.add(user)
        db.flush()
        db.add(BadgeType(id=1, name="VIP", image_url="http://img/vip.png"))
        db.add(
            Assignment(
                badge_type_id=1, user_id=user.id, status="minted", tx_hash="tx-1"
            )
        )
        db.commit()

    r = client.get("/miniapp/badges", headers={"X-Telegram-Init-Data": _init_data(42)})
    assert r.status_code == 200
    badges = r.get_json()
    assert len(badges) == 1
    assert badges[0]["badge_name"] == "VIP"
    assert badges[0]["tx_hash"] == "tx-1"


def test_list_badges_unknown_user_returns_empty(client):
    r = client.get("/miniapp/badges", headers={"X-Telegram-Init-Data": _init_data(99)})
    assert r.status_code == 200
    assert r.get_json() == []
