"""Assignment service — map phone numbers to users and create mint assignments."""

import re

from sqlalchemy.orm import Session

from backend.db.models import Assignment, User

# Assignment statuses
STATUS_PENDING = "pending"
STATUS_QUEUED = "queued"
STATUS_MINTING = "minting"
STATUS_MINTED = "minted"
STATUS_FAILED = "failed"
STATUS_NEEDS_WALLET = "needs_wallet"

VALID_STATUSES = {
    STATUS_PENDING,
    STATUS_QUEUED,
    STATUS_MINTING,
    STATUS_MINTED,
    STATUS_FAILED,
    STATUS_NEEDS_WALLET,
}

# Allowed transitions (current -> allowed next states).
# A missing key means the state is terminal (no outgoing transitions).
TRANSITIONS = {
    STATUS_PENDING: {STATUS_QUEUED, STATUS_FAILED},
    STATUS_QUEUED: {STATUS_MINTING, STATUS_FAILED, STATUS_NEEDS_WALLET},
    STATUS_MINTING: {STATUS_MINTED, STATUS_FAILED},
    STATUS_FAILED: {STATUS_QUEUED, STATUS_PENDING},
    STATUS_NEEDS_WALLET: {STATUS_PENDING},
    STATUS_MINTED: set(),
}


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to digits only."""
    return re.sub(r"\D", "", phone or "")


def transition_assignment(
    assignment: Assignment,
    new_status: str,
) -> None:
    """Transition an assignment to a new status, validating the state machine.

    Raises ValueError if the transition is not allowed.
    """
    if new_status not in VALID_STATUSES:
        raise ValueError(f"unknown status: {new_status}")

    allowed = TRANSITIONS.get(assignment.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"invalid transition: {assignment.status} -> {new_status}"
        )

    assignment.status = new_status


def create_assignments_for_phones(
    db: Session,
    badge_type_id: int,
    phones: list[str],
) -> dict:
    """Create one assignment per recognized phone number.

    Returns a summary dict:
        {created, needs_wallet, no_user, skipped, total}
    """
    summary = {"created": 0, "needs_wallet": 0, "no_user": 0, "skipped": 0, "total": 0}

    for raw_phone in phones:
        phone = normalize_phone(raw_phone)
        if not phone:
            summary["skipped"] += 1
            continue
        summary["total"] += 1

        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            summary["no_user"] += 1
            continue

        # Skip if an assignment for this badge+user already exists
        existing = (
            db.query(Assignment)
            .filter(
                Assignment.badge_type_id == badge_type_id,
                Assignment.user_id == user.id,
            )
            .first()
        )
        if existing:
            summary["skipped"] += 1
            continue

        if user.wallet_address:
            status = STATUS_PENDING
            summary["created"] += 1
        else:
            status = STATUS_NEEDS_WALLET
            summary["needs_wallet"] += 1

        db.add(
            Assignment(
                badge_type_id=badge_type_id,
                user_id=user.id,
                status=status,
            )
        )

    db.commit()
    return summary
