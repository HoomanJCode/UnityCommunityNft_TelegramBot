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
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from backend.db.models import User
from backend.db.session import SessionLocal

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("BOT_TOKEN is not set in .env file")

MINI_APP_URL = os.getenv("MINI_APP_URL", "https://t.me/your_bot/miniapp")


def _phone_keyboard() -> ReplyKeyboardMarkup:
    """Return a keyboard with a 'Share phone number' button."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome the user and request their phone number."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        "Welcome to the UnityCommunity NFT Bot.\n"
        "I can help you receive NFT badges for events you attend.\n\n"
        "To get started, please share your phone number:",
        reply_markup=_phone_keyboard(),
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shared contact — create or update the user record."""
    contact = update.message.contact
    tg_user = update.effective_user
    phone = contact.phone_number.lstrip("+")

    with SessionLocal() as db:
        user = db.query(User).filter(User.telegram_id == tg_user.id).first()
        if user:
            user.phone = phone
            user.username = tg_user.username
        else:
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                phone=phone,
            )
            db.add(user)
        db.commit()

        wallet_kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Connect TON Wallet", url=MINI_APP_URL)]]
        )
        await update.message.reply_text(
            f"✅ Phone number {contact.phone_number} saved!\n\n"
            "Next step: connect your TON wallet to receive NFT badges.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await update.message.reply_text(
            "🔗 Tap below to open the Mini App and connect your Telegram Wallet:",
            reply_markup=wallet_kb,
        )


def main() -> None:
    """Build and run the bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))

    print("🚀 Bot polling started...")
    app.run_polling()


if __name__ == "__main__":
    main()
