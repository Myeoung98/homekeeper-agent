import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, MessageHandler, filters

from homekeeper.ai.assistant import analyze_photo
from homekeeper.db.connection import open_db
from homekeeper.db import member_repo
from homekeeper.db.repairman_repo import get_all_repairmen

logger = logging.getLogger(__name__)

_SEVERITY_EMOJI = {"low": "🟡", "medium": "🟠", "high": "🔴"}


def _is_authenticated(user_id: int, chat_type: str, conn, household_id: int = 0) -> bool:
    import os
    if chat_type in ("group", "supergroup"):
        return True
    try:
        admin_id = int(os.environ.get("ADMIN_USER_ID", ""))
    except ValueError:
        admin_id = None
    if admin_id and user_id == admin_id:
        return True
    members = member_repo.get_all_members(conn, household_id)
    return any(m["telegram_user_id"] == user_id for m in members)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return

    user_id = update.effective_user.id
    chat_type = update.effective_chat.type if update.effective_chat else "private"
    household_id = update.effective_chat.id if update.effective_chat else user_id

    conn = context.bot_data.get("db")
    if conn is None:
        conn = open_db()

    if not _is_authenticated(user_id, chat_type, conn, household_id):
        return

    # Notify immediately before the download (can take 1-2s)
    await update.effective_message.reply_text("🔍 Đang phân tích ảnh...")
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    # Download the largest photo variant
    photo = update.effective_message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    photo_bytes = await tg_file.download_as_bytearray()

    try:
        result = analyze_photo(bytes(photo_bytes))
    except Exception as exc:
        logger.error("Photo analysis failed: %s", exc, exc_info=True)
        await update.effective_message.reply_text(
            "❌ Không thể phân tích ảnh lúc này. Vui lòng mô tả vấn đề bằng text "
            "hoặc dùng /incident để báo sự cố."
        )
        return

    problem = result.get("problem", "Không xác định được vấn đề")
    severity = result.get("severity", "medium")
    service_types: list[str] = result.get("service_types") or []
    advice = result.get("advice", "")
    sev_emoji = _SEVERITY_EMOJI.get(severity, "🟠")
    sev_label = {"low": "Nhẹ", "medium": "Trung bình", "high": "Nghiêm trọng"}.get(severity, severity)

    lines = [
        f"🏠 <b>Kết quả phân tích ảnh</b>\n",
        f"🔍 <b>Vấn đề:</b> {problem}",
        f"{sev_emoji} <b>Mức độ:</b> {sev_label}",
    ]
    if advice:
        lines.append(f"💡 <b>Ghi chú:</b> {advice}")

    # Find matching repairmen
    repairmen = get_all_repairmen(conn, household_id=household_id)
    if not repairmen:
        # Fallback: try global pool (household_id=0)
        repairmen = get_all_repairmen(conn, household_id=0)

    matched = []
    if service_types and repairmen:
        for r in repairmen:
            stype = (r["service_type"] or "").lower()
            if any(st.lower() in stype or stype in st.lower() for st in service_types):
                matched.append(r)

    if matched or repairmen:
        display = matched if matched else list(repairmen)
        lines.append("\n🔧 <b>Thợ gợi ý:</b>")
        for r in display[:3]:
            lines.append(
                f"  👤 <b>{html.escape(r['name'])}</b> — 📞 {html.escape(r['phone'])} "
                f"({html.escape(r['service_type'])})"
            )
        if len(display) > 3:
            lines.append(f"  <i>... và {len(display) - 3} thợ khác — dùng /repairman list</i>")
    elif service_types:
        lines.append(
            f"\n⚠️ Chưa có thợ <b>{', '.join(service_types)}</b> trong danh bạ.\n"
            "Dùng /repairman add để thêm thợ."
        )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("📝 Lưu sự cố & tìm thợ", callback_data="photo_save_incident"),
        InlineKeyboardButton("❌ Bỏ qua", callback_data="photo_dismiss"),
    ]])
    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def photo_incident_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Lưu sự cố' / 'Bỏ qua' buttons from photo analysis."""
    query = update.callback_query
    await query.answer()
    if query.data == "photo_dismiss":
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
        return
    # photo_save_incident — redirect user to /incident
    if query.message:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.reply_text(
            "Dùng /incident và gửi lại ảnh để báo sự cố chính thức và tìm thợ nhé!"
        )


def build_photo_handler():
    from telegram.ext import CallbackQueryHandler
    return [
        MessageHandler(filters.PHOTO, photo_handler),
        CallbackQueryHandler(photo_incident_callback, pattern=r"^photo_(save_incident|dismiss)$"),
    ]
