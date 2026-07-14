import html
import logging
import os

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from homekeeper.bot import _is_group_chat
from homekeeper.db import member_repo

logger = logging.getLogger(__name__)

ASK_ADD_ID, ASK_ADD_NAME, REMOVE_SELECT, REMOVE_CONFIRM = range(4)


async def member_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END

    # Group chats: all members are household members — skip admin check
    if not _is_group_chat(update):
        try:
            admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
        except ValueError:
            return ConversationHandler.END
        if update.effective_user.id != admin_id:
            await update.effective_message.reply_text("Bạn không có quyền quản lý thành viên.")
            return ConversationHandler.END

    household_id = update.effective_chat.id
    context.user_data["household_id"] = household_id

    sub = (context.args or [""])[0].lower()

    if sub == "add":
        await update.effective_message.reply_text(
            "Nhập Telegram user ID của thành viên: (họ cần nhắn tin cho bot trước để lấy ID)"
        )
        return ASK_ADD_ID

    if sub == "list":
        return await _list_members(update, context)

    if sub == "remove":
        return await _start_remove(update, context)

    await update.effective_message.reply_text(
        "Dùng: /member add | list | remove"
    )
    return ConversationHandler.END


# ── List ─────────────────────────────────────────────────────────────────────


async def _list_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        rows = member_repo.get_all_members(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load members: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách thành viên. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thành viên nào. Dùng /member add để thêm."
        )
        return ConversationHandler.END

    lines = [f"👥 <b>Danh sách thành viên</b> ({len(rows)} người):\n"]
    for i, row in enumerate(rows, 1):
        display_name = html.escape(row["name"] or "(không tên)")
        lines.append(f"{i}. <b>{display_name}</b> — ID: {row['telegram_user_id']}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return ConversationHandler.END


# ── Add flow ─────────────────────────────────────────────────────────────────


async def receive_add_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    try:
        telegram_user_id = int(text)
    except ValueError:
        await update.effective_message.reply_text(
            "ID không hợp lệ. Vui lòng nhập một số nguyên (ví dụ: 123456789):"
        )
        return ASK_ADD_ID
    if telegram_user_id <= 0:
        await update.effective_message.reply_text(
            "ID phải là số nguyên dương. Nhập lại:"
        )
        return ASK_ADD_ID

    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        existing = member_repo.get_member_by_telegram_id(conn, telegram_user_id, household_id)
    except Exception as exc:
        logger.error("Failed to check member existence: %s", exc)
        await update.effective_message.reply_text(
            "Không thể kiểm tra danh sách thành viên. Vui lòng thử lại."
        )
        return ConversationHandler.END

    if existing is not None:
        await update.effective_message.reply_text("Thành viên này đã có trong danh sách.")
        return ConversationHandler.END

    context.user_data["add_telegram_id"] = telegram_user_id
    await update.effective_message.reply_text("Nhập tên của thành viên:")
    return ASK_ADD_NAME


async def receive_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if not name:
        await update.effective_message.reply_text("Tên không được để trống. Nhập lại:")
        return ASK_ADD_NAME

    telegram_user_id = context.user_data.get("add_telegram_id")
    household_id = context.user_data.get("household_id", 0)
    if telegram_user_id is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /member add."
        )
        return ConversationHandler.END

    conn = context.application.bot_data["db"]
    try:
        member_repo.add_member(conn, telegram_user_id, name, household_id)
    except Exception as exc:
        logger.error("Failed to save member: %s", exc)
        await update.effective_message.reply_text(
            "Không thể lưu thành viên. Vui lòng thử lại."
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        f"✅ Đã thêm thành viên: <b>{html.escape(name)}</b> (ID: {telegram_user_id}).",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Remove flow ───────────────────────────────────────────────────────────────


async def _start_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        rows = member_repo.get_all_members(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load members for remove: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách thành viên. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thành viên nào. Dùng /member add để thêm."
        )
        return ConversationHandler.END

    lines = ["👥 Chọn số thứ tự thành viên muốn xóa:\n"]
    for i, row in enumerate(rows, 1):
        display_name = html.escape(row["name"] or "(không tên)")
        lines.append(f"{i}. <b>{display_name}</b> — ID: {row['telegram_user_id']}")
    lines.append("\n(hoặc /cancel để hủy)")
    context.user_data["remove_member_ids"] = [row["id"] for row in rows]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return REMOVE_SELECT


async def receive_remove_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    member_ids = context.user_data.get("remove_member_ids", [])
    if not member_ids:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(member_ids)}:"
        )
        return REMOVE_SELECT

    try:
        choice = int(text)
    except ValueError:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(member_ids)}:"
        )
        return REMOVE_SELECT

    if choice < 1 or choice > len(member_ids):
        await update.effective_message.reply_text(
            f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(member_ids)}:"
        )
        return REMOVE_SELECT

    member_id = member_ids[choice - 1]
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        row = member_repo.get_member_by_id(conn, member_id, household_id)
    except Exception as exc:
        logger.error("Failed to fetch member: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải thông tin thành viên. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if row is None:
        await update.effective_message.reply_text(
            "Thành viên không còn tồn tại. Vui lòng bắt đầu lại."
        )
        return ConversationHandler.END

    context.user_data["remove_member"] = {
        "id": row["id"],
        "name": row["name"],
        "telegram_user_id": row["telegram_user_id"],
    }
    await update.effective_message.reply_text(
        f"Bạn có chắc muốn xóa thành viên <b>{html.escape(row['name'] or '(không tên)')}</b>? "
        f"Trả lời 'Có' để xác nhận hoặc 'Không' để hủy.",
        parse_mode="HTML",
    )
    return REMOVE_CONFIRM


async def receive_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    member = context.user_data.get("remove_member")
    household_id = context.user_data.get("household_id", 0)
    if member is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /member remove."
        )
        return ConversationHandler.END

    if text.lower() == "có":
        conn = context.application.bot_data["db"]
        try:
            member_repo.delete_member(conn, member["id"], household_id)
        except Exception as exc:
            logger.error("Failed to delete member: %s", exc)
            await update.effective_message.reply_text(
                "Không thể xóa thành viên. Vui lòng thử lại."
            )
            return ConversationHandler.END
        await update.effective_message.reply_text(
            f"✅ Đã xóa thành viên: <b>{html.escape(member['name'] or '(không tên)')}</b>.",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text("Đã hủy xóa.")
    return ConversationHandler.END


# ── Cancel + Builder ──────────────────────────────────────────────────────────


async def member_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy.")
    return ConversationHandler.END


def build_member_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("member", member_cmd)],
        states={
            ASK_ADD_ID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_id)],
            ASK_ADD_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_name)],
            REMOVE_SELECT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remove_select)],
            REMOVE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remove_confirm)],
        },
        fallbacks=[CommandHandler("cancel", member_cancel)],
    )
