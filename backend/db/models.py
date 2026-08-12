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
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True, index=True)
    wallet_address = Column(String(128), nullable=True)
    wallet_connected_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    attendees = relationship("Attendee", back_populates="user")
    assignments = relationship("Assignment", back_populates="user")

    def __repr__(self):
        return f"<User id={self.id} telegram_id={self.telegram_id}>"


class BadgeType(Base):
    __tablename__ = "badge_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(1024), nullable=True)
    metadata_uri = Column(String(1024), nullable=True)
    is_soulbound = Column(Boolean, default=False, nullable=False)
    collection_address = Column(String(128), nullable=True)
    supply = Column(Integer, default=0, nullable=False)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    events = relationship("Event", back_populates="badge_type")
    assignments = relationship("Assignment", back_populates="badge_type")

    def __repr__(self):
        return f"<BadgeType id={self.id} name={self.name}>"


class Event(Base):
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
    # status: pending → queued → minting → minted | failed | needs_wallet
    tx_hash = Column(String(128), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    minted_at = Column(DateTime(timezone=True), nullable=True)

    badge_type = relationship("BadgeType", back_populates="assignments")
    user = relationship("User", back_populates="assignments")

    def __repr__(self):
        return f"<Assignment id={self.id} status={self.status}>"
