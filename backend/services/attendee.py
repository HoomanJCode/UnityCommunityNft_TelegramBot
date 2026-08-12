"""Attendee service — user joins events."""

from sqlalchemy.orm import Session

from backend.db.models import Attendee, Event, User


def join_event(db: Session, event_id: int, user_id: int) -> tuple[Attendee, bool]:
    """Register a user as an attendee of an event.

    Returns (attendee, created) — `created` is False if already joined.
    Raises ValueError if the event or user does not exist.
    """
    event = db.get(Event, event_id)
    if event is None:
        raise ValueError(f"event {event_id} not found")

    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"user {user_id} not found")

    existing = (
        db.query(Attendee)
        .filter(Attendee.event_id == event_id, Attendee.user_id == user_id)
        .first()
    )
    if existing:
        return existing, False

    attendee = Attendee(event_id=event_id, user_id=user_id)
    db.add(attendee)
    db.commit()
    return attendee, True
