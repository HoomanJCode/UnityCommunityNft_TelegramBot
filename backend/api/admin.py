"""Admin API — badge type & event management (Flask blueprint).

These are the endpoints the admin dashboard (web/admin) will call:
    badge-types  → CRUD for badge designs
    events       → CRUD for events
    assignments  → batch mint jobs (JSON list or CSV upload) + status control

Authentication: every /admin route (except /login and /health) requires a
bearer token obtained from POST /admin/login when `ADMIN_PASSWORD` is set
(see backend/api/auth.py). With no password configured, auth is disabled.
"""

import asyncio
import csv
import hmac
import io
import os
import time
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.api.auth import (
    auth_enabled,
    extract_bearer_token,
    issue_token,
    verify_token,
)
from backend.db.models import Assignment, BadgeType, Event
from backend.db.session import SessionLocal
from backend.services.assignment import (
    create_assignments_for_phones,
    transition_assignment,
)
from backend.services.tonapi import TonAPIClient, from_env as tonapi_from_env

# url_prefix means every route here is mounted under /admin.
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Simple in-memory brute-force brake: track the last login attempt time.
_last_login_attempt: float = 0.0


@admin_bp.before_request
def require_auth():
    """Gate every admin route behind a valid bearer token when auth is on."""
    # The login endpoint must stay open (it issues the tokens), and /health
    # is used by uptime probes that cannot hold a session. /auth/status is
    # the dashboard's boot probe — it must answer before a token exists.
    if not auth_enabled():
        return None
    if request.path in ("/admin/login", "/admin/auth/status", "/health"):
        return None
    if verify_token(extract_bearer_token()):
        return None
    return jsonify({"error": "authentication required"}), 401


@admin_bp.get("/auth/status")
def auth_status():
    """Whether admin auth is enabled — the dashboard's boot probe.

    Kept separate from /login so probing never consumes the login rate
    limiter (which would throttle the operator's first real login attempt).
    """
    return jsonify({"enabled": auth_enabled()})


@admin_bp.post("/login")
def login():
    """Exchange the shared password for a short-lived bearer token."""
    global _last_login_attempt
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    # If no password is configured there is nothing to log into — but a
    # client calling /login then gets a token-free 403 rather than silence.
    if not auth_enabled():
        return jsonify({"error": "admin auth is not enabled (ADMIN_PASSWORD unset)"}), 403

    # Rate limit: one attempt per second prevents fast dictionary attacks.
    now = time.monotonic()
    if now - _last_login_attempt < 1.0:
        return jsonify({"error": "too many attempts, slow down"}), 429
    _last_login_attempt = now

    if not hmac.compare_digest(password.encode(), os.getenv("ADMIN_PASSWORD", "").encode()):
        return jsonify({"error": "invalid password"}), 401

    return jsonify({"token": issue_token()})


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string, or return None."""
    if not value:
        return None
    return datetime.fromisoformat(value)


def _parse_bool(value) -> bool:
    """Coerce a JSON bool or string 'true'/'false' to a Python bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _badge_type_to_dict(bt: BadgeType) -> dict:
    """Serialize a BadgeType row to the JSON shape the dashboard expects."""
    return {
        "id": bt.id,
        "name": bt.name,
        "description": bt.description,
        "image_url": bt.image_url,
        "metadata_uri": bt.metadata_uri,
        "is_soulbound": bt.is_soulbound,
        "collection_address": bt.collection_address,
        "supply": bt.supply,
        "deployed_at": bt.deployed_at.isoformat() if bt.deployed_at else None,
        "created_at": bt.created_at.isoformat() if bt.created_at else None,
    }


# ---------------------------------------------------------------------------
# Badge type CRUD
# ---------------------------------------------------------------------------


@admin_bp.get("/badge-types")
def list_badge_types():
    """List all badge types (newest order is by id, i.e. creation order)."""
    with SessionLocal() as db:
        items = db.query(BadgeType).order_by(BadgeType.id).all()
        return jsonify([_badge_type_to_dict(b) for b in items])


@admin_bp.post("/badge-types")
def create_badge_type():
    """Create a badge type; name is the only required field."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    # Fail fast with a clear 400 instead of saving a nameless badge.
    if not name:
        return jsonify({"error": "name is required"}), 400

    bt = BadgeType(
        name=name,
        description=data.get("description"),
        image_url=data.get("image_url"),
        metadata_uri=data.get("metadata_uri"),
        # is_soulbound decides which contract type gets deployed later.
        is_soulbound=_parse_bool(data.get("is_soulbound", False)),
    )
    with SessionLocal() as db:
        db.add(bt)
        db.commit()
        db.refresh(bt)  # reload to pick up server-generated id/created_at
        return jsonify(_badge_type_to_dict(bt)), 201


@admin_bp.get("/badge-types/<int:badge_type_id>")
def get_badge_type(badge_type_id: int):
    with SessionLocal() as db:
        bt = db.get(BadgeType, badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404
        return jsonify(_badge_type_to_dict(bt))


@admin_bp.put("/badge-types/<int:badge_type_id>")
def update_badge_type(badge_type_id: int):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        bt = db.get(BadgeType, badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404

        for field in ("name", "description", "image_url", "metadata_uri"):
            if field in data:
                setattr(bt, field, data[field])
        if "is_soulbound" in data:
            bt.is_soulbound = _parse_bool(data["is_soulbound"])
        if "collection_address" in data:
            bt.collection_address = data["collection_address"]

        db.commit()
        db.refresh(bt)
        return jsonify(_badge_type_to_dict(bt))


@admin_bp.delete("/badge-types/<int:badge_type_id>")
def delete_badge_type(badge_type_id: int):
    with SessionLocal() as db:
        bt = db.get(BadgeType, badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404
        db.delete(bt)
        db.commit()
        return jsonify({"deleted": badge_type_id})


def _event_to_dict(ev: Event) -> dict:
    return {
        "id": ev.id,
        "name": ev.name,
        "description": ev.description,
        "starts_at": ev.starts_at.isoformat() if ev.starts_at else None,
        "badge_type_id": ev.badge_type_id,
    }


# ---------------------------------------------------------------------------
# Event CRUD
# ---------------------------------------------------------------------------


@admin_bp.get("/events")
def list_events():
    """List all events."""
    with SessionLocal() as db:
        items = db.query(Event).order_by(Event.id).all()
        return jsonify([_event_to_dict(e) for e in items])


@admin_bp.post("/events")
def create_event():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    ev = Event(
        name=name,
        description=data.get("description"),
        starts_at=_parse_datetime(data.get("starts_at")),
        badge_type_id=data.get("badge_type_id"),
    )
    with SessionLocal() as db:
        if ev.badge_type_id and not db.get(BadgeType, ev.badge_type_id):
            return jsonify({"error": "badge_type not found"}), 404
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return jsonify(_event_to_dict(ev)), 201


@admin_bp.get("/events/<int:event_id>")
def get_event(event_id: int):
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            return jsonify({"error": "not found"}), 404
        return jsonify(_event_to_dict(ev))


@admin_bp.put("/events/<int:event_id>")
def update_event(event_id: int):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            return jsonify({"error": "not found"}), 404

        if "name" in data:
            ev.name = data["name"]
        if "description" in data:
            ev.description = data["description"]
        if "starts_at" in data:
            ev.starts_at = _parse_datetime(data["starts_at"])
        if "badge_type_id" in data:
            new_bt_id = data["badge_type_id"]
            if new_bt_id and not db.get(BadgeType, new_bt_id):
                return jsonify({"error": "badge_type not found"}), 404
            ev.badge_type_id = new_bt_id

        db.commit()
        db.refresh(ev)
        return jsonify(_event_to_dict(ev))


@admin_bp.delete("/events/<int:event_id>")
def delete_event(event_id: int):
    with SessionLocal() as db:
        ev = db.get(Event, event_id)
        if not ev:
            return jsonify({"error": "not found"}), 404
        db.delete(ev)
        db.commit()
        return jsonify({"deleted": event_id})


# ---------------------------------------------------------------------------
# Batch mint assignments
# ---------------------------------------------------------------------------


@admin_bp.post("/assignments")
def create_assignments():
    """Create assignments from a JSON list of phone numbers.

    Body: {"badge_type_id": 1, "phones": ["79991112233", ...]}
    The response is a summary dict (created / needs_wallet / skipped / ...).
    """
    data = request.get_json(silent=True) or {}
    badge_type_id = data.get("badge_type_id")
    phones = data.get("phones") or []

    # Validate the request shape before touching the DB.
    if not badge_type_id:
        return jsonify({"error": "badge_type_id is required"}), 400
    if not isinstance(phones, list) or not phones:
        return jsonify({"error": "phones must be a non-empty list"}), 400

    with SessionLocal() as db:
        if not db.get(BadgeType, badge_type_id):
            return jsonify({"error": "badge_type not found"}), 404
        # The heavy lifting (phone → user matching, dedupe) lives in the service.
        summary = create_assignments_for_phones(db, badge_type_id, phones)
    return jsonify(summary), 201


@admin_bp.post("/assignments/upload")
def upload_assignments_csv():
    """Create assignments from an uploaded CSV file.

    The CSV must contain one phone number per line, optionally with a header.
    Form fields: badge_type_id (int), file (CSV upload).
    """
    badge_type_id = request.form.get("badge_type_id", type=int)
    file = request.files.get("file")

    if not badge_type_id:
        return jsonify({"error": "badge_type_id is required"}), 400
    if not file:
        return jsonify({"error": "file is required"}), 400

    # utf-8-sig strips a BOM if present (Excel exports often include one).
    # We only take the first column and ignore any header row.
    text = file.read().decode("utf-8-sig", errors="replace")
    phones = [row[0] for row in csv.reader(io.StringIO(text)) if row]

    with SessionLocal() as db:
        if not db.get(BadgeType, badge_type_id):
            return jsonify({"error": "badge_type not found"}), 404
        summary = create_assignments_for_phones(db, badge_type_id, phones)
    return jsonify(summary), 201


def _assignment_to_dict(a: Assignment) -> dict:
    return {
        "id": a.id,
        "badge_type_id": a.badge_type_id,
        "user_id": a.user_id,
        "status": a.status,
        "tx_hash": a.tx_hash,
        "error": a.error,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "minted_at": a.minted_at.isoformat() if a.minted_at else None,
    }


@admin_bp.get("/assignments")
def list_assignments():
    """List assignments, optionally filtered by ?status=<status>."""
    status = request.args.get("status")
    with SessionLocal() as db:
        q = db.query(Assignment)
        if status:
            q = q.filter(Assignment.status == status)
        items = q.order_by(Assignment.id).all()
        return jsonify([_assignment_to_dict(a) for a in items])


@admin_bp.post("/assignments/<int:assignment_id>/status")
def update_assignment_status(assignment_id: int):
    """Transition an assignment to a new status.

    Body: {"status": "queued"}
    The state machine (see services/assignment.py) rejects illegal jumps.
    """
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "status is required"}), 400

    with SessionLocal() as db:
        a = db.get(Assignment, assignment_id)
        if not a:
            return jsonify({"error": "not found"}), 404
        try:
            transition_assignment(a, new_status)
        except ValueError as e:
            return jsonify({"error": str(e)}), 409
        db.commit()
        db.refresh(a)
        return jsonify(_assignment_to_dict(a))


# ---------------------------------------------------------------------------
# On-chain verification (TonAPI)
# ---------------------------------------------------------------------------


@admin_bp.get("/tonapi/collections/<address>")
def verify_collection(address: str):
    """Verify a deployed collection on-chain via TonAPI.

    Returns the collection's metadata, owner and next item index so an admin
    can confirm a deploy worked before minting. Without a TON_API_KEY the
    endpoint returns 503 so the dashboard can show "TonAPI not configured".
    """
    client: TonAPIClient = tonapi_from_env()
    if not client.enabled:
        return jsonify({"error": "TON_API_KEY is not set"}), 503

    try:
        data = asyncio_run(client.get_collection(address))
    except Exception as e:  # noqa: BLE001 - surface any network/API failure
        return jsonify({"error": f"TonAPI request failed: {e}"}), 502

    metadata = data.get("metadata") or {}
    return jsonify(
        {
            "address": address,
            "name": metadata.get("name"),
            "description": metadata.get("description"),
            "image": metadata.get("image"),
            "owner": (data.get("owner") or {}).get("address"),
            "next_item_index": data.get("next_item_index"),
            "verified": data.get("verified", False),
        }
    )


@admin_bp.get("/tonapi/accounts/<address>/balance")
def account_balance(address: str):
    """Return a wallet's balance (in TON) via TonAPI."""
    client: TonAPIClient = tonapi_from_env()
    if not client.enabled:
        return jsonify({"error": "TON_API_KEY is not set"}), 503

    try:
        balance_nano = asyncio_run(client.get_balance(address))
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": f"TonAPI request failed: {e}"}), 502

    return jsonify({"address": address, "balance_ton": balance_nano / 1e9})
