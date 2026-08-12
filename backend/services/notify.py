"""Telegram notifier — sends mint outcome messages to users."""


class TelegramNotifier:
    """Wraps a python-telegram-bot Bot to send notifications."""

    def __init__(self, bot) -> None:
        self.bot = bot

    async def notify(self, telegram_id: int, text: str) -> None:
        """Send a message to the given Telegram user."""
        await self.bot.send_message(chat_id=telegram_id, text=text)
