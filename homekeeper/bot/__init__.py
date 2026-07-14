import logging
import os
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def _is_group_chat(update: Update) -> bool:
    """Return True if the update comes from a group or supergroup chat."""
    return update.effective_chat is not None and update.effective_chat.type in (
        "group",
        "supergroup",
    )


def admin_only(func):
    """Rejects non-admin callers before the handler runs.
    In group/supergroup chats all members are considered household members and are allowed.
    In private chats the ADMIN_USER_ID check is enforced.
    Apply to every CommandHandler callback and ConversationHandler entry point.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return

        # Group chats: all members are household members — skip admin check
        if _is_group_chat(update):
            return await func(update, context)

        admin_id_str = os.environ.get("ADMIN_USER_ID")
        if not admin_id_str:
            logger.error("ADMIN_USER_ID not configured")
            return
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            logger.error("ADMIN_USER_ID is not a valid integer: %r", admin_id_str)
            return

        if update.effective_user.id != admin_id:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Bạn không có quyền sử dụng bot này."
                )
            return
        return await func(update, context)
    return wrapper
