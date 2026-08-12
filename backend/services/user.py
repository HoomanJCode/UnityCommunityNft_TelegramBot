"""User service — create/update user records.

Two entry points use this: the bot (onboarding via /start + phone share) and
the Mini App (wallet linking).
"""

from datetime import datetime, timezone

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
        # User exists → refresh only the fields we were actually given.
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


def link_wallet(
    db: Session,
    telegram_id: int,
    wallet_address: str,
) -> User | None:
    """Link a TON wallet address to a user's record.

    Creates the user if they don't exist yet (the Mini App can be opened
    before /start). Returns None if the wallet address is empty.
    The caller owns the commit.
    """
    wallet_address = (wallet_address or "").strip()
    if not wallet_address:
        return None

    user = upsert_user(db, telegram_id=telegram_id)
    user.wallet_address = wallet_address
    # Timestamp lets the admin see how fresh a linked wallet is.
    user.wallet_connected_at = datetime.now(timezone.utc)
    return user
