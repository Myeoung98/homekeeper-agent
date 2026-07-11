import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from homekeeper.db import incident_repo, member_repo, repairman_repo
from homekeeper.domain import matching

logger = logging.getLogger(__name__)

ASK_DESC = 0

INCIDENT_YES_PATTERN = r'^incident_yes:\d+$'
INCIDENT_NO_PATTERN = r'^incident_no$'


def _is_authenticated(user_id: int, conn) -> bool:
    admin_id_str = os.environ.get("ADMIN_USER_ID", "")
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        logger.error("ADMIN_USER_ID is not a valid integer: %r", admin_id_str)
        admin_id = None
    if admin_id is not None and user_id == admin_id:
        return True
    members = member_repo.get_all_members(conn)
    return any(m["telegram_user_id"] == user_id for m in members)


async def incident_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END
    user_id = update.effective_user.id
    conn = context.application.bot_data["db"]
    if not _is_authenticated(user_id, conn):
        await update.effective_message.reply_text("Bạn không có quyền sử dụng bot này.")
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "Mô tả sự cố: (ví dụ: điều hòa phòng ngủ không mát)"
    )
    return ASK_DESC


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip()
    if not text:
        await update.effective_message.reply_text("Mô tả không được để trống. Nhập lại:")
        return ASK_DESC

    if update.effective_user is None:
        return ConversationHandler.END
    user_id = update.effective_user.id
    conn = context.application.bot_data["db"]
    try:
        incident_id = incident_repo.create_incident(conn, reported_by=user_id, description=text)
    except Exception as exc:
        logger.error("Failed to save incident: %s", exc)
        await update.effective_message.reply_text("Không thể lưu sự cố. Vui lòng thử lại.")
        return ASK_DESC

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Có", callback_data=f"incident_yes:{incident_id}"),
            InlineKeyboardButton("Không", callback_data="incident_no"),
        ]
    ])
    await update.effective_message.reply_text(
        "Bạn có cần tìm thợ sửa không?",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def incident_yes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    try:
        incident_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        if query.message is not None:
            await query.message.edit_text("Dữ liệu không hợp lệ.")
        return

    if update.effective_user is None:
        return

    conn = context.application.bot_data["db"]

    if not _is_authenticated(update.effective_user.id, conn):
        if query.message is not None:
            await query.message.edit_text("Bạn không có quyền sử dụng bot này.")
        return

    try:
        incident = incident_repo.get_incident_by_id(conn, incident_id)
    except Exception as exc:
        logger.error("Failed to load incident %s: %s", incident_id, exc)
        if query.message is not None:
            await query.message.edit_text("Không thể tải thông tin sự cố. Vui lòng thử lại.")
        return

    if incident is None:
        if query.message is not None:
            await query.message.edit_text("Không tìm thấy sự cố.")
        return

    try:
        repairmen = repairman_repo.get_all_repairmen(conn)
    except Exception as exc:
        logger.error("Failed to load repairmen: %s", exc)
        if query.message is not None:
            await query.message.edit_text("Không thể tải danh bạ thợ. Vui lòng thử lại.")
        return

    if not repairmen:
        if query.message is not None:
            await query.message.edit_text(
                "Danh bạ thợ đang trống. Admin có thể thêm thợ bằng /repairman add."
            )
        return

    matches = matching.match_repairmen(incident["description"], repairmen)

    if not matches:
        if query.message is not None:
            await query.message.edit_text(
                "Không tìm thấy thợ phù hợp trong danh bạ. Bạn có thể thêm thợ bằng /repairman add."
            )
        return

    lines = ["🔧 Thợ sửa gợi ý:\n"]
    for i, r in enumerate(matches, 1):
        lines.append(f"{i}. {r['name']} — {r['service_type']} — {r['phone']}")
    lines.append("\nLiên hệ trực tiếp với thợ theo số điện thoại trên.")

    if query.message is not None:
        await query.message.edit_text("\n".join(lines))


async def incident_no_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.message is not None:
        await query.message.edit_text("✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ.")


async def incident_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy.")
    return ConversationHandler.END


def build_incident_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("incident", incident_cmd)],
        states={
            ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
        },
        fallbacks=[CommandHandler("cancel", incident_cancel)],
    )
