"""UnityCommunityNftBot — Telegram bot entry point."""

import os
import sys

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from backend.db.models import Event, User
from backend.db.session import SessionLocal
from backend.services.assignment import normalize_phone
from backend.services.attendee import join_event
from backend.services.user import upsert_user

load_dotenv()

# A bot without a token is useless — fail loudly at startup, not later.
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("BOT_TOKEN is not set in .env file")

# Where the wallet-connect Mini App lives (t.me/<bot>/<app> or a web URL).
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://t.me/your_bot/miniapp")


def _phone_keyboard() -> ReplyKeyboardMarkup:
    """Return a keyboard with a 'Share phone number' button.

    request_contact=True makes Telegram hand the user's phone straight to the
    bot (with the user's consent) instead of them typing it.
    """
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome the user and request their phone number."""
    user = update.effective_user
    await update.effective_message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        "Welcome to the UnityCommunity NFT Bot.\n"
        "I can help you receive NFT badges for events you attend.\n\n"
        "To get started, please share your phone number:",
        reply_markup=_phone_keyboard(),
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shared contact — create or update the user record.

    This is the core onboarding step: it links the Telegram identity to a phone
    number, which is exactly what admins later use to target badge mints.
    """
    message = update.effective_message
    contact = message.contact
    tg_user = update.effective_user
    # Normalize so "+7 999 111-22-33" matches the digits-only admin uploads.
    phone = normalize_phone(contact.phone_number)

    # Upsert (not insert): a returning user gets their phone refreshed.
    with SessionLocal() as db:
        upsert_user(
            db,
            telegram_id=tg_user.id,
            username=tg_user.username,
            phone=phone,
        )
        db.commit()

    # Step two of onboarding: point the user at the Mini App to connect a wallet.
    wallet_kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔗 Connect TON Wallet", url=MINI_APP_URL)]]
    )
    await message.reply_text(
        f"✅ Phone number {contact.phone_number} saved!\n\n"
        "Next step: connect your TON wallet to receive NFT badges.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.reply_text(
        "🔗 Tap below to open the Mini App and connect your Telegram Wallet:",
        reply_markup=wallet_kb,
    )


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join — list available events for the user to join."""
    with SessionLocal() as db:
        events = db.query(Event).order_by(Event.id).all()

    if not events:
        await update.effective_message.reply_text(
            "😕 No events are available right now. Check back later!"
        )
        return

    keyboard = [
        [InlineKeyboardButton(e.name, callback_data=f"join:{e.id}")]
        for e in events
    ]
    await update.effective_message.reply_text(
        "📅 Choose an event to join:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_join_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle an event-selection callback from /join."""
    query = update.callback_query
    await query.answer()

    try:
        event_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Invalid selection.")
        return

    tg_user = update.effective_user
    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if user is None:
            await query.edit_message_text(
                "⚠️ Please share your phone number first with /start."
            )
            return

        try:
            _, created = join_event(db, event_id=event_id, user_id=user.id)
        except ValueError:
            await query.edit_message_text("❌ Event not found.")
            return

    if created:
        await query.edit_message_text("🎉 You've joined the event! See you there.")
    else:
        await query.edit_message_text("✅ You've already joined this event.")


def main() -> None:
    """Build and run the bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    # Handler registration order matters little here, but the callback pattern
    # must match exactly what /join sends as callback_data ("join:<id>").
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(CallbackQueryHandler(handle_join_callback, pattern=r"^join:"))

    print("🚀 Bot polling started...")
    app.run_polling()


if __name__ == "__main__":
    main()
