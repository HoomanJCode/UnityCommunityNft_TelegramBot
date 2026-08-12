"""Admin API — badge type & event management (Flask blueprint)."""

from flask import Blueprint, jsonify, request

from backend.db.models import BadgeType
from backend.db.session import SessionLocal

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


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
        is_soulbound=bool(data.get("is_soulbound", False)),
    )
    with SessionLocal() as db:
        db.add(bt)
        db.commit()
        db.refresh(bt)
        return jsonify(_badge_type_to_dict(bt)), 201


@admin_bp.get("/badge-types/<int:badge_type_id>")
def get_badge_type(badge_type_id: int):
    with SessionLocal() as db:
        bt = db.query(BadgeType).get(badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404
        return jsonify(_badge_type_to_dict(bt))


@admin_bp.put("/badge-types/<int:badge_type_id>")
def update_badge_type(badge_type_id: int):
    data = request.get_json(silent=True) or {}
    with SessionLocal() as db:
        bt = db.query(BadgeType).get(badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404

        for field in ("name", "description", "image_url", "metadata_uri"):
            if field in data:
                setattr(bt, field, data[field])
        if "is_soulbound" in data:
            bt.is_soulbound = bool(data["is_soulbound"])
        if "collection_address" in data:
            bt.collection_address = data["collection_address"]

        db.commit()
        db.refresh(bt)
        return jsonify(_badge_type_to_dict(bt))


@admin_bp.delete("/badge-types/<int:badge_type_id>")
def delete_badge_type(badge_type_id: int):
    with SessionLocal() as db:
        bt = db.query(BadgeType).get(badge_type_id)
        if not bt:
            return jsonify({"error": "not found"}), 404
        db.delete(bt)
        db.commit()
        return jsonify({"deleted": badge_type_id})
