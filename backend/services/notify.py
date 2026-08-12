"""Telegram notifier — sends mint outcome messages to users.

Used by the mint worker: on a successful mint the user gets a "🎉 your badge
was minted" message; on a final failure (after all retries) a "❌" message.
"""


class TelegramNotifier:
    """Wraps a python-telegram-bot Bot to send notifications.

    The worker depends on the `Notifier` protocol (async notify), and this
    class is the real Telegram implementation of it.
    """

    def __init__(self, bot) -> None:
        self.bot = bot

    async def notify(self, telegram_id: int, text: str) -> None:
        """Send a message to the given Telegram user."""
        await self.bot.send_message(chat_id=telegram_id, text=text)
