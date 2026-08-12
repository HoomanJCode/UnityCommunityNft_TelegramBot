"""Admin authentication — shared-password login issuing a bearer token.

This is deliberately simple (Phase 5 scope): a single shared password
(`ADMIN_PASSWORD`) that the operator sets. On a correct login the server
issues a short-lived, stateless bearer token (signed with the password itself)
that the dashboard sends as `Authorization: Bearer <token>`.

Security posture:
- When `ADMIN_PASSWORD` is unset/empty, auth is **disabled** so local dev and
  the existing test suite keep working without a token.
- Tokens expire after `TOKEN_TTL_SECONDS` and are invalidated immediately if
  the password changes (they are signed with it).
- Login is rate-limited lightly in-memory to slow brute-forcing.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 12 * 60 * 60  # 12 hours — matches a working day
LOGIN_RATE_LIMIT_SECONDS = 1.0  # min gap between login attempts


def admin_password() -> str:
    """The configured shared admin password ('' means auth is disabled)."""
    return os.getenv("ADMIN_PASSWORD", "")


def auth_enabled() -> bool:
    """Auth only kicks in when the operator actually set a password."""
    return bool(admin_password())


def _sign(payload: str) -> str:
    """HMAC-SHA256 signature of the payload using the password as the key."""
    return hmac.new(
        admin_password().encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def issue_token() -> str:
    """Issue a signed token carrying its own expiry timestamp."""
    payload = json.dumps({"exp": int(time.time()) + TOKEN_TTL_SECONDS})
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(encoded)}"


def verify_token(token: str | None) -> bool:
    """Return True if the token is well-formed, unexpired and correctly signed."""
    if not token:
        return False
    try:
        encoded, signature = token.split(".", 1)
        # Constant-time compare so a bad signature doesn't leak timing info.
        if not hmac.compare_digest(_sign(encoded), signature):
            return False
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        return payload.get("exp", 0) > int(time.time())
    except (ValueError, json.JSONDecodeError, KeyError):
        return False


def extract_bearer_token() -> str | None:
    """Pull the token from the Flask request's Authorization header."""
    from flask import request

    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None
