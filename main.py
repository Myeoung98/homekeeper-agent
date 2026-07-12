from dotenv import load_dotenv

load_dotenv()  # must run before any os.environ access

import logging
import os
import sys

from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from homekeeper.bot import admin_only
from homekeeper.bot.incident_handlers import (
    INCIDENT_NO_PATTERN,
    INCIDENT_YES_PATTERN,
    build_incident_conversation,
    incident_no_callback,
    incident_yes_callback,
)
from homekeeper.bot.reminder_callbacks import CALLBACK_PATTERN, handle_reminder_callback
from homekeeper.bot.demo_handlers import build_demo_handlers
from homekeeper.bot.member_handlers import build_member_conversation
from homekeeper.bot.repairman_handlers import build_repairman_conversation
from homekeeper.bot.task_handlers import (
    build_add_conversation,
    build_delete_conversation,
    build_edit_conversation,
    list_handler,
)
from homekeeper.bot.ai_handlers import build_ai_handler
from homekeeper.db.connection import open_db
from homekeeper.scheduler.catchup import run_catchup
from homekeeper.scheduler.loop import start_scheduler

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@admin_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🏠 <b>HomeKeeper Agent</b> đang hoạt động!\n\n"
        "📋 <b>Quản lý công việc</b>\n"
        "  /add — Thêm công việc bảo trì\n"
        "  /list — Xem danh sách\n"
        "  /edit — Sửa công việc\n"
        "  /delete — Xóa công việc\n\n"
        "👥 <b>Thành viên gia đình</b>\n"
        "  /member add — Thêm thành viên\n"
        "  /member list — Xem danh sách\n"
        "  /member remove — Xóa thành viên\n\n"
        "🔧 <b>Thợ sửa chữa</b>\n"
        "  /repairman add — Thêm thợ\n"
        "  /repairman list — Xem danh sách\n\n"
        "🚨 <b>Báo sự cố</b>\n"
        "  /incident — Báo sự cố & tìm thợ\n\n"
        "📊 <b>Tổng quan</b>\n"
        "  /status — Dashboard hệ thống\n"
        "  /remind &lt;id&gt; — Gửi reminder ngay",
        parse_mode="HTML",
    )


def main() -> None:
    admin_id = os.environ.get("ADMIN_USER_ID")
    db_path = os.environ.get("DB_PATH")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    groq_key = os.environ.get("GROQ_API_KEY")

    missing = [k for k, v in [
        ("ADMIN_USER_ID", admin_id),
        ("DB_PATH", db_path),
        ("TELEGRAM_BOT_TOKEN", token),
        ("GROQ_API_KEY", groq_key),
    ] if not v]

    if missing:
        logger.error("Missing required env vars: %s — check your .env file", ", ".join(missing))
        sys.exit(1)

    try:
        app_db = open_db()  # schema init + persistent PTB-thread connection
    except Exception as exc:
        logger.error("DB initialisation failed: %s", exc)
        sys.exit(1)

    application = ApplicationBuilder().token(token).build()
    application.bot_data["db"] = app_db
    application.add_handler(build_add_conversation())
    application.add_handler(build_edit_conversation())
    application.add_handler(build_delete_conversation())
    application.add_handler(build_repairman_conversation())
    application.add_handler(build_member_conversation())
    application.add_handler(build_incident_conversation())
    application.add_handler(CommandHandler("list", list_handler))
    application.add_handler(CommandHandler("start", start_handler))
    for h in build_demo_handlers():
        application.add_handler(h)
    application.add_handler(
        CallbackQueryHandler(
            handle_reminder_callback,
            pattern=CALLBACK_PATTERN,
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            incident_no_callback,
            pattern=INCIDENT_NO_PATTERN,
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            incident_yes_callback,
            pattern=INCIDENT_YES_PATTERN,
        )
    )

    try:
        run_catchup(app_db)
    except Exception as exc:
        logger.warning("Catch-up scan failed: %s — continuing", exc)

    start_scheduler()

    # AI catch-all handler must be last (lowest priority)
    application.add_handler(build_ai_handler())

    logger.info("HomeKeeper Agent started")
    application.run_polling()


if __name__ == "__main__":
    main()
