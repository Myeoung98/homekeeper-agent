import logging

from telegram import Update
from telegram.ext import ChatMemberHandler, ContextTypes

logger = logging.getLogger(__name__)


async def on_bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sent when bot is added to a group chat — kick off household onboarding."""
    result = update.my_chat_member
    if not result:
        return

    # Only fire when bot transitions from non-member to member/admin
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status
    if old_status in ("member", "administrator") or new_status not in ("member", "administrator"):
        return

    chat = result.chat
    if chat.type not in ("group", "supergroup"):
        return

    welcome = (
        "🏠 <b>Chào mừng HomeKeeper đến với nhóm!</b>\n\n"
        "Tôi là trợ lý quản lý nhà thông minh cho hộ gia đình này.\n\n"
        "📋 <b>Bắt đầu nhanh:</b>\n"
        "  /start — Xem hướng dẫn đầy đủ\n"
        "  /add — Thêm lịch bảo trì\n"
        "  /repairman add — Thêm thợ sửa chữa\n\n"
        "🤖 <b>AI thông minh:</b>\n"
        "  • Nhắn tin tự nhiên: <i>\"nhắc tôi vệ sinh máy lạnh sau 90 ngày\"</i>\n"
        "  • Gửi ảnh hỏng hóc → tôi nhận dạng và gợi ý thợ ngay\n"
        "  • Hỏi bất cứ điều gì về bảo trì nhà\n\n"
        "👥 Mọi thành viên trong nhóm đều có thể dùng đầy đủ tính năng.\n\n"
        "<i>Dữ liệu nhóm này được lưu riêng, không chia sẻ với nhóm khác.</i>"
    )

    try:
        await context.bot.send_message(
            chat_id=chat.id,
            text=welcome,
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Onboarding message failed for chat %d: %s", chat.id, exc)


def build_onboarding_handler() -> ChatMemberHandler:
    return ChatMemberHandler(on_bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER)
