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

from homekeeper.ai.assistant import analyze_photo
from homekeeper.bot import _is_group_chat
from homekeeper.db import incident_repo, member_repo, repairman_repo
from homekeeper.db import repairman_rating_repo
from homekeeper.domain import matching

logger = logging.getLogger(__name__)

ASK_DESC = 0

INCIDENT_YES_PATTERN = r'^incident_yes:\d+$'
INCIDENT_NO_PATTERN = r'^incident_no$'
RATE_REPAIRMAN_PATTERN = r'^rate_r:\d+:\d+:\d+$'


def _is_authenticated(user_id: int, conn, household_id: int = 0, is_group: bool = False) -> bool:
    # In group chats all members are authenticated
    if is_group:
        return True
    admin_id_str = os.environ.get("ADMIN_USER_ID", "")
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        logger.error("ADMIN_USER_ID is not a valid integer: %r", admin_id_str)
        admin_id = None
    if admin_id is not None and user_id == admin_id:
        return True
    members = member_repo.get_all_members(conn, household_id)
    return any(m["telegram_user_id"] == user_id for m in members)


async def incident_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END
    user_id = update.effective_user.id
    household_id = update.effective_chat.id
    conn = context.application.bot_data["db"]
    if not _is_authenticated(user_id, conn, household_id, _is_group_chat(update)):
        await update.effective_message.reply_text("Bạn không có quyền sử dụng bot này.")
        return ConversationHandler.END
    context.user_data["household_id"] = household_id
    await update.effective_message.reply_text(
        "Mô tả sự cố bằng text hoặc gửi ảnh thiết bị hỏng:"
    )
    return ASK_DESC


async def _save_and_ask_repairman(
    update: Update,
    description: str,
    user_id: int,
    household_id: int,
    conn,
    extra_text: str = "",
) -> int:
    try:
        incident_id = incident_repo.create_incident(
            conn, reported_by=user_id, description=description, household_id=household_id
        )
    except Exception as exc:
        logger.error("Failed to save incident: %s", exc)
        await update.effective_message.reply_text("Không thể lưu sự cố. Vui lòng thử lại.")
        return ASK_DESC

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Có", callback_data=f"incident_yes:{incident_id}"),
        InlineKeyboardButton("Không", callback_data="incident_no"),
    ]])
    msg = extra_text + "\nBạn có cần tìm thợ sửa không?" if extra_text else "Bạn có cần tìm thợ sửa không?"
    await update.effective_message.reply_text(msg, reply_markup=keyboard)
    return ConversationHandler.END


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip()
    if not text:
        await update.effective_message.reply_text("Mô tả không được để trống. Nhập lại:")
        return ASK_DESC

    if update.effective_user is None:
        return ConversationHandler.END
    user_id = update.effective_user.id
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    return await _save_and_ask_repairman(update, text, user_id, household_id, conn)


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle photo sent during incident report — use Vision AI to generate description."""
    if update.effective_user is None:
        return ConversationHandler.END

    user_id = update.effective_user.id
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]

    await update.effective_message.reply_text("🔍 Đang phân tích ảnh...")

    photo = update.effective_message.photo[-1]
    try:
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        result = analyze_photo(bytes(photo_bytes))
        description = result.get("problem", "Sự cố từ ảnh")
        severity = result.get("severity", "medium")
        advice = result.get("advice", "")
        sev_label = {"low": "🟢 Thấp", "medium": "🟠 Trung bình", "high": "🔴 Cao"}.get(severity, severity)
        extra = f"🔍 <b>AI nhận diện:</b> {description}\n{sev_label}"
        if advice:
            extra += f"\n💡 {advice}"
    except Exception as exc:
        logger.warning("Photo analysis failed: %s", exc)
        description = "Sự cố từ ảnh (không phân tích được)"
        extra = ""

    return await _save_and_ask_repairman(
        update, description, user_id, household_id, conn, extra_text=extra
    )


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

    household_id = update.effective_chat.id if update.effective_chat else 0
    conn = context.application.bot_data["db"]

    if not _is_authenticated(
        update.effective_user.id, conn, household_id, _is_group_chat(update)
    ):
        if query.message is not None:
            await query.message.edit_text("Bạn không có quyền sử dụng bot này.")
        return

    try:
        incident = incident_repo.get_incident_by_id(conn, incident_id, household_id)
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
        repairmen = repairman_repo.get_all_repairmen(conn, household_id)
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
        avg, cnt = repairman_rating_repo.get_avg_rating(conn, r["id"], household_id)
        rating_str = f"  ⭐ {avg}/5 ({cnt} đánh giá)" if avg else ""
        lines.append(f"{i}. <b>{r['name']}</b> — {r['service_type']} — {r['phone']}{rating_str}")
    lines.append("\nLiên hệ trực tiếp với thợ theo số điện thoại trên.")
    lines.append("\n💬 Sau khi dùng dịch vụ, đánh giá thợ:")

    # Rating buttons for first matched repairman
    top = matches[0]
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"⭐ {s}", callback_data=f"rate_r:{top['id']}:{s}:{incident_id}")
        for s in range(1, 6)
    ]])

    if query.message is not None:
        await query.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)


async def incident_no_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.message is not None:
        await query.message.edit_text("✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ.")


async def rate_repairman_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rate_r:{repairman_id}:{stars}:{incident_id} callback."""
    query = update.callback_query
    await query.answer()
    try:
        _, repairman_id_str, stars_str, incident_id_str = query.data.split(":")
        repairman_id = int(repairman_id_str)
        stars = int(stars_str)
        incident_id = int(incident_id_str)
    except (ValueError, AttributeError):
        return

    household_id = update.effective_chat.id if update.effective_chat else 0
    conn = context.application.bot_data["db"]
    repairman_rating_repo.add_rating(
        conn, repairman_id=repairman_id, stars=stars,
        household_id=household_id, incident_id=incident_id,
    )
    star_str = "⭐" * stars
    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"{star_str} Đã lưu đánh giá <b>{stars}/5</b> sao. Cảm ơn!",
            parse_mode="HTML",
        )


async def incident_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy.")
    return ConversationHandler.END


def build_incident_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("incident", incident_cmd)],
        states={
            ASK_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description),
                MessageHandler(filters.PHOTO, receive_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", incident_cancel)],
    )
