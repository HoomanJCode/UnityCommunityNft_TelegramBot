"""Mini App API — TON wallet linking and badge gallery (Flask blueprint)."""

import os

from flask import Blueprint, jsonify, request

from backend.db.models import Assignment, BadgeType, User
from backend.db.session import SessionLocal
from backend.services.initdata import extract_telegram_id, verify_init_data
from backend.services.user import link_wallet

mini_app_bp = Blueprint("mini_app", __name__, url_prefix="/miniapp")


def _bot_token() -> str:
    return os.getenv("BOT_TOKEN", "")


def _authenticated_telegram_id() -> int | None:
    """Verify initData from header or body; return the Telegram user id."""
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        body = request.get_json(silent=True) or {}
        init_data = body.get("init_data") or body.get("initData")
    fields = verify_init_data(init_data, _bot_token())
    return extract_telegram_id(fields)


@mini_app_bp.post("/wallet")
def link_wallet_endpoint():
    """Link the user's TON wallet address.

    Body: {"init_data": "<telegram initData>", "wallet_address": "EQ..."}
    """
    data = request.get_json(silent=True) or {}
    telegram_id = _authenticated_telegram_id()
    if telegram_id is None:
        return jsonify({"error": "invalid init_data"}), 401

    wallet_address = (data.get("wallet_address") or "").strip()
    if not wallet_address:
        return jsonify({"error": "wallet_address is required"}), 400

    with SessionLocal() as db:
        user = link_wallet(db, telegram_id, wallet_address)
        db.commit()
        return jsonify(
            {
                "telegram_id": telegram_id,
                "wallet_address": user.wallet_address,
                "wallet_connected_at": (
                    user.wallet_connected_at.isoformat()
                    if user.wallet_connected_at
                    else None
                ),
            }
        )


@mini_app_bp.get("/badges")
def list_badges():
    """Return the badges (minted assignments) owned by the user."""
    telegram_id = _authenticated_telegram_id()
    if telegram_id is None:
        return jsonify({"error": "invalid init_data"}), 401

    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user is None:
            return jsonify([])

        rows = (
            db.query(Assignment, BadgeType)
            .join(BadgeType, Assignment.badge_type_id == BadgeType.id)
            .filter(
                Assignment.user_id == user.id,
                Assignment.status == "minted",
            )
            .order_by(Assignment.minted_at.desc())
            .all()
        )

        badges = [
            {
                "assignment_id": assignment.id,
                "badge_name": badge.name,
                "description": badge.description,
                "image_url": badge.image_url,
                "tx_hash": assignment.tx_hash,
                "minted_at": (
                    assignment.minted_at.isoformat()
                    if assignment.minted_at
                    else None
                ),
            }
            for assignment, badge in rows
        ]
    return jsonify(badges)
