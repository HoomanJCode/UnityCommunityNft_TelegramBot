"""Tests for the user service (upsert_user)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base, User
from backend.services.user import upsert_user


@pytest.fixture()
def db():
    """Create an in-memory SQLite database for each test."""
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


def test_upsert_creates_new_user(db):
    user = upsert_user(db, telegram_id=123, username="alice", phone="79991112233")
    db.commit()

    saved = db.query(User).filter(User.telegram_id == 123).first()
    assert saved is not None
    assert saved.phone == "79991112233"
    assert saved.username == "alice"


def test_upsert_updates_existing_user_phone(db):
    upsert_user(db, telegram_id=123, username="alice", phone="79991112233")
    db.commit()

    upsert_user(db, telegram_id=123, username="alice", phone="79995556677")
    db.commit()

    saved = db.query(User).filter(User.telegram_id == 123).first()
    assert saved.phone == "79995556677"
    # Should still be a single row
    assert db.query(User).count() == 1


def test_upsert_allows_null_phone(db):
    user = upsert_user(db, telegram_id=456, username="bob")
    db.commit()

    saved = db.query(User).filter(User.telegram_id == 456).first()
    assert saved is not None
    assert saved.phone is None
    assert saved.username == "bob"
