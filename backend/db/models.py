"""SQLAlchemy ORM models for the badge system.

The core chain the app relies on:
    phone number → User → wallet_address → minted Assignment (badge)

`users`      — everyone who chatted with the bot (identified by telegram_id)
`badge_types`— a badge design; one on-chain collection per row
`events`     — a real-world event a badge is handed out for
`attendees`  — users who joined an event (join table)
`assignments`— a "one badge of type X for user Y" job with a mint status
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware).

    Used as the default for created_at columns. Storing tz-aware UTC avoids
    the pitfalls of naive local times when minting/notifying across zones.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base — every model inherits from it."""

    pass


class User(Base):
    """A person who interacted with the bot.

    telegram_id is the stable key (never changes for a user); phone is what
    admins use to target mints; wallet_address is the mint destination.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    # TON wallet linked via the Mini App; None until the user connects one.
    wallet_address = Column(String(128), nullable=True)
    wallet_connected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    attendees = relationship("Attendee", back_populates="user")
    assignments = relationship("Assignment", back_populates="user")

    def __repr__(self):
        return f"<User id={self.id} telegram_id={self.telegram_id}>"


class BadgeType(Base):
    """A badge design (name, art, soulbound flag) + its on-chain collection.

    One collection contract is deployed per badge type — that is what lets
    admins choose "transferable" or "soulbound" per badge at creation time.
    """

    __tablename__ = "badge_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    # Off-chain metadata URI, forwarded to the on-chain mint as item content.
    metadata_uri = Column(String(1024), nullable=True)
    # Contract-level property: TEP-62 (transferable) vs TEP-85 (soulbound).
    is_soulbound = Column(Boolean, default=False, nullable=False)
    # Filled in after the collection contract is deployed to the network.
    collection_address = Column(String(128), nullable=True)
    supply = Column(Integer, default=0, nullable=False)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    events = relationship("Event", back_populates="badge_type")
    assignments = relationship("Assignment", back_populates="badge_type")

    def __repr__(self):
        return f"<BadgeType id={self.id} name={self.name}>"


class Event(Base):
    """A real-world event that hands out a badge.

    Links to a badge_type; users join via the /join bot command.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    badge_type_id = Column(Integer, ForeignKey("badge_types.id"), nullable=True)

    badge_type = relationship("BadgeType", back_populates="events")
    attendees = relationship("Attendee", back_populates="event")

    def __repr__(self):
        return f"<Event id={self.id} name={self.name}>"


class Attendee(Base):
    """Join table: which users registered for which event."""

    __tablename__ = "attendees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    event = relationship("Event", back_populates="attendees")
    user = relationship("User", back_populates="attendees")

    def __repr__(self):
        return f"<Attendee event_id={self.event_id} user_id={self.user_id}>"


class Assignment(Base):
    """A mint job: "give user X one badge of type Y".

    status drives the whole pipeline:
        pending → queued → minting → minted | failed | needs_wallet
    retry_count tracks how many times the worker tried (see worker.py).
    """

    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    badge_type_id = Column(Integer, ForeignKey("badge_types.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )
    # Incremented on each failed mint attempt; capped by MAX_RETRIES.
    retry_count = Column(Integer, default=0, nullable=False)
    # On-chain transaction hash, filled in by the worker on success.
    tx_hash = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    minted_at = Column(DateTime(timezone=True), nullable=True)

    badge_type = relationship("BadgeType", back_populates="assignments")
    user = relationship("User", back_populates="assignments")

    def __repr__(self):
        return f"<Assignment id={self.id} status={self.status}>"
