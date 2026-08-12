"""Tests for Telegram Mini App initData verification."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from backend.services.initdata import extract_telegram_id, verify_init_data

BOT_TOKEN = "123456:ABC-DEF"


def _make_init_data(bot_token: str, fields: dict) -> str:
    """Build a signed initData string for the given fields."""
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    sig = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode({**fields, "hash": sig})


def test_verify_valid_init_data():
    user = {"id": 42, "first_name": "Alice"}
    init_data = _make_init_data(
        BOT_TOKEN,
        {"auth_date": "1700000000", "user": json.dumps(user)},
    )

    fields = verify_init_data(init_data, BOT_TOKEN)

    assert fields is not None
    assert fields["user"] == user
    assert fields["auth_date"] == "1700000000"


def test_extract_telegram_id():
    fields = {"user": {"id": 42}}
    assert extract_telegram_id(fields) == 42
    assert extract_telegram_id(None) is None
    assert extract_telegram_id({"user": None}) is None


def test_verify_rejects_tampered_data():
    # Core security property: any edit to the data breaks the HMAC, so a
    # MITM cannot change the user id or auth_date of a captured initData.
    init_data = _make_init_data(
        BOT_TOKEN,
        {"auth_date": "1700000000", "user": json.dumps({"id": 42})},
    )
    tampered = init_data.replace("1700000000", "1700000001")
    assert verify_init_data(tampered, BOT_TOKEN) is None


def test_verify_rejects_wrong_token():
    init_data = _make_init_data(
        BOT_TOKEN,
        {"auth_date": "1700000000", "user": json.dumps({"id": 42})},
    )
    assert verify_init_data(init_data, "different-token") is None


def test_verify_rejects_missing_hash():
    assert verify_init_data("auth_date=1700000000", BOT_TOKEN) is None
    assert verify_init_data("", BOT_TOKEN) is None


def test_verify_rejects_stale_init_data():
    # Replay protection: a signed-but-ancient initData must be refused.
    old = str(int(time.time()) - 100000)  # way older than max_age
    init_data = _make_init_data(
        BOT_TOKEN, {"auth_date": old, "user": json.dumps({"id": 42})}
    )
    assert verify_init_data(init_data, BOT_TOKEN, max_age=60) is None


def test_verify_accepts_fresh_init_data():
    now = str(int(time.time()))
    init_data = _make_init_data(
        BOT_TOKEN, {"auth_date": now, "user": json.dumps({"id": 42})}
    )
    assert verify_init_data(init_data, BOT_TOKEN, max_age=60) is not None
