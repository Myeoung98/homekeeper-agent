from dotenv import load_dotenv

load_dotenv()  # must run before any os.environ access

import asyncio
import logging
import os
import sys
import threading

import uvicorn
from telegram import BotCommand, Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from homekeeper.bot import admin_only
from homekeeper.bot.expense_handlers import build_expense_handlers
from homekeeper.bot.incident_handlers import (
    INCIDENT_NO_PATTERN,
    INCIDENT_YES_PATTERN,
    RATE_REPAIRMAN_PATTERN,
    build_incident_conversation,
    incident_no_callback,
    incident_yes_callback,
    rate_repairman_callback,
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
from homekeeper.bot.photo_handlers import build_photo_handler
from homekeeper.bot.onboarding_handlers import build_onboarding_handler
from homekeeper.dashboard.app import create_app as create_dashboard
from homekeeper.db.connection import open_db
from homekeeper.scheduler.catchup import run_catchup
from homekeeper.scheduler.loop import start_scheduler

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import os
    user_id = update.effective_user.id if update.effective_user else None
    try:
        admin_id = int(os.environ.get("ADMIN_USER_ID", ""))
    except ValueError:
        admin_id = None
    is_admin = (user_id == admin_id)

    if is_admin:
        text = (
            "🏠 <b>HomeKeeper Agent</b> — Trợ lý nhà thông minh\n\n"
            "🤖 <b>AI tự nhiên</b>\n"
            "  💬 Nhắn text bất kỳ — bot tự hiểu\n"
            "  📸 Gửi ảnh hỏng hóc — bot nhận dạng & gợi ý thợ\n\n"
            "📋 <b>Quản lý công việc</b>\n"
            "  /add — Thêm lịch bảo trì\n"
            "  /list — Xem danh sách\n"
            "  /edit — Sửa   /delete — Xóa\n\n"
            "🔧 <b>Thợ sửa chữa</b>\n"
            "  /repairman add | list\n\n"
            "👥 <b>Thành viên</b>\n"
            "  /member add | list | remove\n\n"
            "🚨 <b>Báo sự cố</b>\n"
            "  /incident — Mô tả hoặc gửi ảnh, tìm thợ phù hợp\n\n"
            "💰 <b>Chi phí</b>\n"
            "  /expense &lt;số tiền&gt; — Ghi chi phí\n"
            "  /expense — Xem tổng hợp 6 tháng\n\n"
            "📊 <b>Tổng quan</b>\n"
            "  /status — Dashboard tổng quan\n\n"
            "💡 <i>Gõ /cancel bất cứ lúc nào để hủy thao tác đang dở.</i>\n"
            "<i>👥 Thêm bot vào group gia đình để cả nhà cùng dùng!</i>"
        )
    else:
        text = (
            "🏠 <b>HomeKeeper Agent</b> — Trợ lý nhà thông minh\n\n"
            "Bạn có thể:\n"
            "  💬 Nhắn text tự nhiên — bot tự hiểu\n"
            "  📸 Gửi ảnh thiết bị hỏng — bot nhận dạng\n"
            "  /incident — Báo sự cố & tìm thợ\n"
            "  /list — Xem lịch bảo trì\n"
            "  /expense — Chi phí bảo trì\n\n"
            "<i>Liên hệ admin gia đình nếu cần thêm quyền.</i>"
        )
    await update.effective_message.reply_text(text, parse_mode="HTML")


def main() -> None:
    admin_id = os.environ.get("ADMIN_USER_ID")
    db_path = os.environ.get("DB_PATH")
    token = os.environ.get("TELEGRAM_BOT_TOKEN")

    groq_key = os.environ.get("GROQ_API_KEY")
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    missing = [k for k, v in [
        ("ADMIN_USER_ID", admin_id),
        ("DB_PATH", db_path),
        ("TELEGRAM_BOT_TOKEN", token),
        ("GROQ_API_KEY", groq_key),
        ("OPENROUTER_API_KEY", openrouter_key),
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
    application.add_handler(
        CallbackQueryHandler(
            rate_repairman_callback,
            pattern=RATE_REPAIRMAN_PATTERN,
        )
    )
    for h in build_expense_handlers():
        application.add_handler(h)

    try:
        run_catchup(app_db)
    except Exception as exc:
        logger.warning("Catch-up scan failed: %s — continuing", exc)

    start_scheduler()

    # Group onboarding — fires when bot is added to a group
    application.add_handler(build_onboarding_handler())

    # Photo analysis — before AI text catch-all
    for h in build_photo_handler():
        application.add_handler(h)

    # AI text catch-all must be last (lowest priority)
    application.add_handler(build_ai_handler())

    # Start web dashboard in a background thread
    port = int(os.environ.get("PORT", 8080))
    dash_app = create_dashboard()

    def _run_dashboard():
        uvicorn.run(dash_app, host="0.0.0.0", port=port, log_level="warning")

    dashboard_thread = threading.Thread(target=_run_dashboard, daemon=True)
    dashboard_thread.start()
    logger.info("Dashboard running on port %d", port)

    # Register bot command menu (shows when user types "/")
    async def _set_commands(_app):
        await _app.bot.set_my_commands([
            BotCommand("start",     "Xem hướng dẫn & danh sách lệnh"),
            BotCommand("list",      "Danh sách công việc bảo trì"),
            BotCommand("add",       "Thêm công việc mới"),
            BotCommand("edit",      "Sửa công việc"),
            BotCommand("delete",    "Xóa công việc"),
            BotCommand("incident",  "Báo sự cố & tìm thợ"),
            BotCommand("repairman", "Quản lý danh bạ thợ"),
            BotCommand("member",    "Quản lý thành viên gia đình"),
            BotCommand("expense",   "Ghi/xem chi phí bảo trì"),
            BotCommand("status",    "Tổng quan dashboard"),
        ])
        logger.info("Bot command menu registered")

    application.post_init = _set_commands

    logger.info("HomeKeeper Agent started")
    application.run_polling()


if __name__ == "__main__":
    main()
