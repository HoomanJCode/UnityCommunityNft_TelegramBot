"""Telegram notifier — sends mint outcome messages to users.

Used by the mint worker: on a successful mint the user gets a "🎉 your badge
was minted" message; on a final failure (after all retries) a "❌" message.
"""


class TelegramNotifier:
    """Wraps a python-telegram-bot Bot to send notifications.

    The worker depends on the `Notifier` protocol (async notify + alert_admin),
    and this class is the real Telegram implementation of it.
    """

    def __init__(self, bot, admin_chat_id: int | None = None) -> None:
        self.bot = bot
        # Chat id of the operator that receives 🚨 admin alerts; None disables
        # them (e.g. local dev without an admin account).
        self.admin_chat_id = admin_chat_id

    async def notify(self, telegram_id: int, text: str) -> None:
        """Send a message to the given Telegram user."""
        await self.bot.send_message(chat_id=telegram_id, text=text)

    async def alert_admin(self, text: str) -> None:
        """Send an alert to the operator's chat (no-op if not configured)."""
        if self.admin_chat_id is not None:
            await self.bot.send_message(chat_id=self.admin_chat_id, text=text)
