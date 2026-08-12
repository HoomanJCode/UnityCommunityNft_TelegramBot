"""UnityCommunityNftBot — Telegram bot entry point."""

import asyncio
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("BOT_TOKEN is not set in .env file")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome the user."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}!\n\n"
        "Welcome to the UnityCommunity NFT Bot.\n"
        "I can help you receive NFT badges for events you attend."
    )


def main() -> None:
    """Build and run the bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))

    print("🚀 Bot polling started...")
    app.run_polling()


if __name__ == "__main__":
    main()
