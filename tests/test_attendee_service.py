"""Tests for the attendee service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.models import Attendee, Base, Event, User
from backend.services.attendee import join_event


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


def _seed(db):
    db.add(User(id=1, telegram_id=111))
    db.add(Event(id=1, name="Meetup"))
    db.commit()


def test_join_event_creates_attendee(db):
    _seed(db)
    attendee, created = join_event(db, event_id=1, user_id=1)
    assert created is True
    assert attendee.event_id == 1
    assert attendee.user_id == 1
    assert db.query(Attendee).count() == 1


def test_join_event_is_idempotent(db):
    _seed(db)
    join_event(db, 1, 1)
    attendee, created = join_event(db, 1, 1)
    assert created is False
    assert db.query(Attendee).count() == 1


def test_join_event_missing_event(db):
    _seed(db)
    with pytest.raises(ValueError):
        join_event(db, event_id=999, user_id=1)


def test_join_event_missing_user(db):
    _seed(db)
    with pytest.raises(ValueError):
        join_event(db, event_id=1, user_id=999)
