"""UnityCommunityNftBot — Telegram bot entry point."""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("BOT_TOKEN is not set in .env file")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    """Handle /start — welcome the user."""
    await message.answer(
        f"👋 Hello, {message.from_user.first_name}!\n\n"
        "Welcome to the UnityCommunity NFT Bot.\n"
        "I can help you receive NFT badges for events you attend."
    )


async def main() -> None:
    print("🚀 Bot polling started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
