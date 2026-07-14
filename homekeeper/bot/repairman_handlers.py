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
from homekeeper.db import repairman_repo

logger = logging.getLogger(__name__)

ASK_ADD_NAME, ASK_ADD_PHONE, ASK_ADD_SERVICE, \
    EDIT_SELECT, EDIT_NAME, EDIT_PHONE, EDIT_SERVICE, \
    DELETE_SELECT, DELETE_CONFIRM = range(9)


def _is_keep_old(text: str) -> bool:
    return text.strip() in ("", "-")


async def repairman_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END

    # Group chats: all members are household members — skip admin check
    if not _is_group_chat(update):
        try:
            admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
        except ValueError:
            return ConversationHandler.END
        if update.effective_user.id != admin_id:
            await update.effective_message.reply_text("Bạn không có quyền quản lý danh bạ thợ.")
            return ConversationHandler.END

    household_id = update.effective_chat.id
    context.user_data["household_id"] = household_id

    sub = (context.args or [""])[0].lower()

    if sub == "add":
        await update.effective_message.reply_text("Tên thợ là gì?")
        return ASK_ADD_NAME

    if sub == "list":
        return await _list_repairmen(update, context)

    if sub == "edit":
        return await _start_edit(update, context)

    if sub == "delete":
        return await _start_delete(update, context)

    await update.effective_message.reply_text(
        "Dùng: /repairman add | list | edit | delete"
    )
    return ConversationHandler.END


# ── List ─────────────────────────────────────────────────────────────────────


async def _list_repairmen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        rows = repairman_repo.get_all_repairmen(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load repairmen: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh bạ thợ. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thợ nào trong danh bạ. Dùng /repairman add để thêm."
        )
        return ConversationHandler.END

    lines = [f"🔧 <b>Danh bạ thợ</b> ({len(rows)} người):\n"]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. <b>{html.escape(row['name'])}</b> — {html.escape(row['phone'])} — {html.escape(row['service_type'])}"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return ConversationHandler.END


# ── Add flow ─────────────────────────────────────────────────────────────────


async def receive_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if not name:
        await update.effective_message.reply_text("Tên không được để trống. Nhập lại:")
        return ASK_ADD_NAME
    context.user_data["add_name"] = name
    await update.effective_message.reply_text("Số điện thoại của thợ?")
    return ASK_ADD_PHONE


async def receive_add_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.effective_message.text.strip()
    if not phone:
        await update.effective_message.reply_text("Số điện thoại không được để trống. Nhập lại:")
        return ASK_ADD_PHONE
    context.user_data["add_phone"] = phone
    await update.effective_message.reply_text(
        "Loại dịch vụ? (ví dụ: điều hòa, điện lạnh)"
    )
    return ASK_ADD_SERVICE


async def receive_add_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_type = update.effective_message.text.strip()
    if not service_type:
        await update.effective_message.reply_text("Loại dịch vụ không được để trống. Nhập lại:")
        return ASK_ADD_SERVICE

    name = context.user_data.get("add_name")
    phone = context.user_data.get("add_phone")
    household_id = context.user_data.get("household_id", 0)
    if not name or not phone:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /repairman add."
        )
        return ConversationHandler.END

    conn = context.application.bot_data["db"]
    try:
        repairman_repo.create_repairman(conn, name, phone, service_type, household_id)
    except Exception as exc:
        logger.error("Failed to save repairman: %s", exc)
        await update.effective_message.reply_text(
            "Không thể lưu thông tin thợ. Vui lòng thử lại."
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        f"✅ Đã thêm thợ: <b>{html.escape(name)}</b> — {html.escape(phone)} — {html.escape(service_type)}.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Edit flow ────────────────────────────────────────────────────────────────


async def _start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        rows = repairman_repo.get_all_repairmen(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load repairmen for edit: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh bạ thợ. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thợ nào trong danh bạ để sửa. Dùng /repairman add để thêm."
        )
        return ConversationHandler.END

    lines = ["🔧 Chọn số thứ tự thợ muốn sửa:\n"]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. <b>{html.escape(row['name'])}</b> — {html.escape(row['phone'])} — {html.escape(row['service_type'])}"
        )
    lines.append("\n(hoặc /cancel để hủy)")
    context.user_data["edit_repairman_ids"] = [row["id"] for row in rows]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return EDIT_SELECT


async def receive_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman_ids = context.user_data.get("edit_repairman_ids", [])
    if not text.isdigit() or not repairman_ids:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(repairman_ids)}:"
        )
        return EDIT_SELECT

    choice = int(text)
    if choice < 1 or choice > len(repairman_ids):
        await update.effective_message.reply_text(
            f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(repairman_ids)}:"
        )
        return EDIT_SELECT

    repairman_id = repairman_ids[choice - 1]
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        row = repairman_repo.get_repairman_by_id(conn, repairman_id, household_id)
    except Exception as exc:
        logger.error("Failed to fetch repairman: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải thông tin thợ. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if row is None:
        await update.effective_message.reply_text(
            "Thợ không còn tồn tại. Vui lòng bắt đầu lại."
        )
        return ConversationHandler.END

    context.user_data["edit_repairman"] = dict(row)
    await update.effective_message.reply_text(
        f"Tên hiện tại: <b>{html.escape(row['name'])}</b>.\n"
        f"Nhập tên mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_NAME


async def receive_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman = context.user_data.get("edit_repairman")
    if repairman is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /repairman edit."
        )
        return ConversationHandler.END

    context.user_data["edit_name"] = repairman["name"] if _is_keep_old(text) else text
    await update.effective_message.reply_text(
        f"Số điện thoại hiện tại: <b>{html.escape(repairman['phone'])}</b>.\n"
        f"Nhập số mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_PHONE


async def receive_edit_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman = context.user_data.get("edit_repairman")
    if repairman is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /repairman edit."
        )
        return ConversationHandler.END

    context.user_data["edit_phone"] = repairman["phone"] if _is_keep_old(text) else text
    await update.effective_message.reply_text(
        f"Loại dịch vụ hiện tại: <b>{html.escape(repairman['service_type'])}</b>.\n"
        f"Nhập loại dịch vụ mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_SERVICE


async def receive_edit_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman = context.user_data.get("edit_repairman")
    new_name = context.user_data.get("edit_name")
    new_phone = context.user_data.get("edit_phone")
    household_id = context.user_data.get("household_id", 0)
    if repairman is None or new_name is None or new_phone is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /repairman edit."
        )
        return ConversationHandler.END

    new_service = repairman["service_type"] if _is_keep_old(text) else text
    conn = context.application.bot_data["db"]
    try:
        repairman_repo.update_repairman(
            conn, repairman["id"], new_name, new_phone, new_service, household_id
        )
    except Exception as exc:
        logger.error("Failed to update repairman: %s", exc)
        await update.effective_message.reply_text(
            "Không thể cập nhật thông tin thợ. Vui lòng thử lại."
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        f"✅ Đã cập nhật thợ: <b>{html.escape(new_name)}</b> — {html.escape(new_phone)} — {html.escape(new_service)}.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ── Delete flow ──────────────────────────────────────────────────────────────


async def _start_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        rows = repairman_repo.get_all_repairmen(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load repairmen for delete: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh bạ thợ. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thợ nào trong danh bạ để xóa."
        )
        return ConversationHandler.END

    lines = ["🔧 Chọn số thứ tự thợ muốn xóa:\n"]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. <b>{html.escape(row['name'])}</b> — {html.escape(row['phone'])} — {html.escape(row['service_type'])}"
        )
    lines.append("\n(hoặc /cancel để hủy)")
    context.user_data["delete_repairman_ids"] = [row["id"] for row in rows]
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return DELETE_SELECT


async def receive_delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman_ids = context.user_data.get("delete_repairman_ids", [])
    if not text.isdigit() or not repairman_ids:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(repairman_ids)}:"
        )
        return DELETE_SELECT

    choice = int(text)
    if choice < 1 or choice > len(repairman_ids):
        await update.effective_message.reply_text(
            f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(repairman_ids)}:"
        )
        return DELETE_SELECT

    repairman_id = repairman_ids[choice - 1]
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        row = repairman_repo.get_repairman_by_id(conn, repairman_id, household_id)
    except Exception as exc:
        logger.error("Failed to fetch repairman: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải thông tin thợ. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if row is None:
        await update.effective_message.reply_text(
            "Thợ không còn tồn tại. Vui lòng bắt đầu lại."
        )
        return ConversationHandler.END

    context.user_data["delete_repairman"] = {"id": row["id"], "name": row["name"]}
    await update.effective_message.reply_text(
        f"Bạn có chắc muốn xóa thợ <b>{html.escape(row['name'])}</b>? "
        f"Trả lời 'Có' để xác nhận hoặc 'Không' để hủy.",
        parse_mode="HTML",
    )
    return DELETE_CONFIRM


async def receive_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    repairman = context.user_data.get("delete_repairman")
    household_id = context.user_data.get("household_id", 0)
    if repairman is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /repairman delete."
        )
        return ConversationHandler.END

    if text.lower() == "có":
        conn = context.application.bot_data["db"]
        try:
            repairman_repo.delete_repairman(conn, repairman["id"], household_id)
        except Exception as exc:
            logger.error("Failed to delete repairman: %s", exc)
            await update.effective_message.reply_text(
                "Không thể xóa thợ. Vui lòng thử lại."
            )
            return ConversationHandler.END
        await update.effective_message.reply_text(
            f"✅ Đã xóa thợ: <b>{html.escape(repairman['name'])}</b>",
            parse_mode="HTML",
        )
    else:
        await update.effective_message.reply_text("Đã hủy xóa.")
    return ConversationHandler.END


# ── Cancel + Builder ──────────────────────────────────────────────────────────


async def repairman_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy.")
    return ConversationHandler.END


def build_repairman_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("repairman", repairman_cmd)],
        states={
            ASK_ADD_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_name)],
            ASK_ADD_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_phone)],
            ASK_ADD_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_service)],
            EDIT_SELECT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_select)],
            EDIT_NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_name)],
            EDIT_PHONE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_phone)],
            EDIT_SERVICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_service)],
            DELETE_SELECT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_select)],
            DELETE_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_confirm)],
        },
        fallbacks=[CommandHandler("cancel", repairman_cancel)],
    )
