"""Telegram Mini App initData verification.

Validates the HMAC signature Telegram attaches to Mini App requests so the
backend can trust the identity (`user.id`) without a login flow.

Algorithm (https://core.telegram.org/bots/webapps#validating-data):
    1. drop the `hash` field
    2. sort remaining fields alphabetically
    3. data_check_string = "key=value" pairs joined by newlines
    4. secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    5. expected  = HMAC_SHA256(key=secret_key, msg=data_check_string)
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


def verify_init_data(
    init_data: str,
    bot_token: str,
    max_age: int | None = None,
) -> dict | None:
    """Verify Mini App initData and return the parsed fields.

    Returns a dict of fields (with `user` decoded to a dict) on success,
    or None if the signature is invalid / missing / stale.

    `max_age` (seconds) rejects initData older than this to prevent replay.
    """
    if not init_data or not bot_token:
        return None

    # The `hash` field is the signature — pop it before building the string
    # that must be signed, otherwise the hashes would never match.
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        return None

    # Step 2-3 of the Telegram algorithm: sort pairs and join with newlines.
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items())
    )
    # Step 4: derive the secret from the bot token, then HMAC the string.
    secret_key = hmac.new(
        b"WebAppData", bot_token.encode(), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # compare_digest is constant-time — don't replace with `==`.
    if not hmac.compare_digest(expected_hash, received_hash):
        return None

    # Replay protection: a validly-signed but old initData string must be
    # rejected, otherwise an attacker could reuse a captured one forever.
    if max_age is not None:
        try:
            auth_date = int(fields.get("auth_date", 0))
        except (ValueError, TypeError):
            return None
        if auth_date <= 0 or time.time() - auth_date > max_age:
            return None

    # Telegram sends `user` as a JSON string; decode it for convenience.
    user_raw = fields.get("user")
    if user_raw:
        try:
            fields["user"] = json.loads(user_raw)
        except json.JSONDecodeError:
            fields["user"] = None

    return fields


def extract_telegram_id(fields: dict | None) -> int | None:
    """Pull the Telegram user id from parsed initData fields."""
    if not fields:
        return None
    user = fields.get("user")
    if isinstance(user, dict):
        return user.get("id")
    return None
