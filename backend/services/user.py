"""User service — create/update user records."""

from sqlalchemy.orm import Session

from backend.db.models import User


def upsert_user(
    db: Session,
    telegram_id: int,
    username: str | None = None,
    phone: str | None = None,
) -> User:
    """Create a user if missing, otherwise update their phone/username.

    Returns the persisted user (uncommitted — caller owns the commit).
    """
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        if phone is not None:
            user.phone = phone
        if username is not None:
            user.username = username
    else:
        user = User(
            telegram_id=telegram_id,
            username=username,
            phone=phone,
        )
        db.add(user)
    return user
