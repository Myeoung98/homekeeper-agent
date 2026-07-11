import asyncio
import os

from telegram import Bot


def send_telegram_message(chat_id: int, text: str, reply_markup=None) -> None:
    """Send a Telegram message from the scheduler thread.

    Creates a fresh event loop via asyncio.run() — safe to call from a sync thread.
    Reads TELEGRAM_BOT_TOKEN from env on each call (no shared Bot instance).
    Raises on Telegram API error — callers are responsible for catching.
    No imports from homekeeper.bot (AD-1).
    reply_markup: optional InlineKeyboardMarkup (passed for admin D-0 sends; None for members and D-1).
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    async def _send() -> None:
        async with Bot(token) as bot:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

    asyncio.run(_send())
