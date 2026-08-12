"""UnityCommunityNftBot — Telegram bot entry point."""

import os
import sys

from dotenv import load_dotenv
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("BOT_TOKEN is not set in .env file")


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


def main() -> None:
    """Build and run the bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))

    print("🚀 Bot polling started...")
    app.run_polling()


if __name__ == "__main__":
    main()
