import logging
import os
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def admin_only(func):
    """Rejects non-admin callers before the handler runs.
    Apply to every CommandHandler callback and ConversationHandler entry point.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return

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
