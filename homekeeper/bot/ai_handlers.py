import logging
import os
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from homekeeper.ai.assistant import analyze_message
from homekeeper.bot import _is_group_chat
from homekeeper.db.connection import open_db
from homekeeper.db import member_repo
from homekeeper.db.repairman_repo import get_all_repairmen
from homekeeper.db.task_repo import create_task

logger = logging.getLogger(__name__)


def _is_authenticated(
    user_id: int,
    conn,
    household_id: int = 0,
    is_group: bool = False,
) -> bool:
    # In group chats all members are authenticated
    if is_group:
        return True
    admin_id_str = os.environ.get("ADMIN_USER_ID", "")
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        admin_id = None
    if admin_id is not None and user_id == admin_id:
        return True
    members = member_repo.get_all_members(conn, household_id)
    return any(m["telegram_user_id"] == user_id for m in members)


def _is_admin(user_id: int) -> bool:
    try:
        return user_id == int(os.environ.get("ADMIN_USER_ID", ""))
    except ValueError:
        return False


async def ai_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return

    user_id = update.effective_user.id
    text = update.effective_message.text or ""
    household_id = update.effective_chat.id if update.effective_chat else 0

    conn = context.bot_data.get("db")
    if conn is None:
        conn = open_db()

    if not _is_authenticated(user_id, conn, household_id, _is_group_chat(update)):
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        result = analyze_message(text)
    except Exception as exc:
        logger.error("AI analysis error: %s", exc)
        await update.effective_message.reply_text(
            "❌ Không thể xử lý yêu cầu. Vui lòng thử lại sau."
        )
        return

    intent = result.get("intent", "general")

    if intent == "create_task":
        await _handle_create_task(update, result, conn, user_id, household_id)
    elif intent == "find_repairman":
        await _handle_find_repairman(update, result, conn, household_id)
    else:
        answer = result.get(
            "answer",
            "Tôi có thể giúp bạn:\n• Đặt lịch bảo trì: 'nhắc tôi thay filter máy lạnh sau 90 ngày'\n• Tìm thợ: 'điều hòa nhà tôi bị chảy nước'",
        )
        await update.effective_message.reply_text(f"🏠 {answer}")


async def _handle_create_task(
    update,
    result,
    conn,
    user_id: int,
    household_id: int = 0,
) -> None:
    if not _is_admin(user_id):
        await update.effective_message.reply_text(
            "⚠️ Chỉ admin mới có thể tạo công việc bảo trì.\n"
            "Dùng /incident để báo sự cố và tìm thợ nhé!"
        )
        return

    task_name = result.get("task_name") or "Công việc bảo trì"
    cycle_days = int(result.get("cycle_days") or 30)
    next_due = (datetime.now(timezone.utc) + timedelta(days=cycle_days)).strftime("%Y-%m-%d")

    task_id = create_task(conn, task_name, cycle_days, next_due, household_id)

    await update.effective_message.reply_text(
        f"✅ <b>Đã tạo công việc bảo trì!</b>\n\n"
        f"📋 <b>{task_name}</b>\n"
        f"🔄 Chu kỳ nhắc: mỗi {cycle_days} ngày\n"
        f"📅 Lần nhắc tới: {next_due}\n"
        f"🆔 Mã số: #{task_id}\n\n"
        f"<i>Dùng /list để xem tất cả công việc.</i>",
        parse_mode="HTML",
    )


async def _handle_find_repairman(
    update,
    result,
    conn,
    household_id: int = 0,
) -> None:
    problem = result.get("problem_description", "")
    suggested_types: list[str] = result.get("suggested_service_types") or []

    repairmen = get_all_repairmen(conn, household_id)
    if not repairmen:
        await update.effective_message.reply_text(
            "⚠️ Chưa có thợ nào trong hệ thống.\n"
            "Admin có thể thêm thợ qua lệnh /repairman add."
        )
        return

    matched = []
    if suggested_types:
        for r in repairmen:
            stype = (r["service_type"] or "").lower()
            if any(st.lower() in stype or stype in st.lower() for st in suggested_types):
                matched.append(r)

    display = matched if matched else list(repairmen)

    lines = ["🔧 <b>Gợi ý thợ sửa chữa</b>"]
    if problem:
        lines.append(f"📝 <i>{problem}</i>\n")

    for r in display[:5]:
        lines.append(
            f"👤 <b>{r['name']}</b>\n"
            f"   📞 {r['phone']}\n"
            f"   🛠 {r['service_type']}"
        )

    if len(display) > 5:
        lines.append(f"\n<i>... và {len(display) - 5} thợ khác. Dùng /repairman list để xem thêm.</i>")
    elif not matched and suggested_types:
        lines.append("\n<i>Không tìm thấy thợ chuyên môn phù hợp, hiển thị tất cả thợ.</i>")

    await update.effective_message.reply_text("\n\n".join(lines), parse_mode="HTML")


def build_ai_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, ai_message_handler)
