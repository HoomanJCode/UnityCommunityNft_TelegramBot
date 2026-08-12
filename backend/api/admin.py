"""Admin API — badge type & event management (Flask blueprint)."""

import csv
import io
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend.db.models import Assignment, BadgeType, Event
from backend.db.session import SessionLocal
from backend.services.assignment import (
    create_assignments_for_phones,
    transition_assignment,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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


@admin_bp.get("/badge-types")
def list_badge_types():
    with SessionLocal() as db:
        items = db.query(BadgeType).order_by(BadgeType.id).all()
        return jsonify([_badge_type_to_dict(b) for b in items])


@admin_bp.post("/badge-types")
def create_badge_type():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    bt = BadgeType(
        name=name,
        description=data.get("description"),
        image_url=data.get("image_url"),
        metadata_uri=data.get("metadata_uri"),
        is_soulbound=_parse_bool(data.get("is_soulbound", False)),
    )
    with SessionLocal() as db:
        db.add(bt)
        db.commit()
        db.refresh(bt)
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


@admin_bp.get("/events")
def list_events():
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


@admin_bp.post("/assignments")
def create_assignments():
    """Create assignments from a JSON list of phone numbers.

    Body: {"badge_type_id": 1, "phones": ["79991112233", ...]}
    """
    data = request.get_json(silent=True) or {}
    badge_type_id = data.get("badge_type_id")
    phones = data.get("phones") or []

    if not badge_type_id:
        return jsonify({"error": "badge_type_id is required"}), 400
    if not isinstance(phones, list) or not phones:
        return jsonify({"error": "phones must be a non-empty list"}), 400

    with SessionLocal() as db:
        if not db.get(BadgeType, badge_type_id):
            return jsonify({"error": "badge_type not found"}), 404
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
