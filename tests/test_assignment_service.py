"""Tests for the assignment service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Assignment, Base, BadgeType, User
from backend.services.assignment import (
    STATUS_FAILED,
    STATUS_MINTED,
    STATUS_MINTING,
    STATUS_NEEDS_WALLET,
    STATUS_PENDING,
    STATUS_QUEUED,
    create_assignments_for_phones,
    normalize_phone,
    transition_assignment,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_normalize_phone():
    assert normalize_phone("+7 999 111-22-33") == "79991112233"
    assert normalize_phone("79991112233") == "79991112233"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


def test_create_assignments_handles_all_cases(db):
    db.add(User(telegram_id=1, phone="79991112233"))  # no wallet
    db.add(User(telegram_id=2, phone="79995556677", wallet_address="EQD..."))
    db.commit()

    summary = create_assignments_for_phones(
        db,
        badge_type_id=1,
        phones=["+7 999 111-22-33", "79995556677", "000000", ""],
    )

    assert summary["created"] == 1      # wallet user -> pending
    assert summary["needs_wallet"] == 1  # no-wallet user
    assert summary["no_user"] == 1       # unknown phone
    assert summary["skipped"] == 1       # empty phone

    rows = db.query(Assignment).all()
    assert len(rows) == 2
    statuses = {r.status for r in rows}
    assert statuses == {STATUS_PENDING, STATUS_NEEDS_WALLET}


def test_create_assignments_skips_duplicates(db):
    db.add(User(telegram_id=1, phone="79991112233", wallet_address="EQD..."))
    db.commit()

    create_assignments_for_phones(db, 1, ["79991112233"])
    summary = create_assignments_for_phones(db, 1, ["79991112233"])

    assert summary["skipped"] == 1
    assert db.query(Assignment).count() == 1


def test_transition_assignment_valid_and_invalid(db):
    a = Assignment(badge_type_id=1, user_id=1, status=STATUS_PENDING)

    transition_assignment(a, STATUS_QUEUED)
    assert a.status == STATUS_QUEUED

    transition_assignment(a, STATUS_MINTING)
    assert a.status == STATUS_MINTING

    transition_assignment(a, STATUS_MINTED)
    assert a.status == STATUS_MINTED


def test_transition_assignment_rejects_invalid(db):
    a = Assignment(badge_type_id=1, user_id=1, status=STATUS_QUEUED)
    with pytest.raises(ValueError):
        transition_assignment(a, STATUS_MINTED)  # can't skip minting


def test_transition_assignment_rejects_unknown_status(db):
    a = Assignment(badge_type_id=1, user_id=1, status=STATUS_PENDING)
    with pytest.raises(ValueError):
        transition_assignment(a, "bogus")
