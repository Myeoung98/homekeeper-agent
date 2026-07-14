import html
import logging
import re
from datetime import date, datetime, timedelta

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from homekeeper.bot import admin_only
from homekeeper.db import task_repo

logger = logging.getLogger(__name__)

ASK_NAME, ASK_CYCLE, ASK_DATE = range(3)
EDIT_SELECT, EDIT_NAME, EDIT_CYCLE, EDIT_DATE = range(3, 7)
DELETE_SELECT, DELETE_CONFIRM = range(7, 9)

MAX_TASK_NAME_LEN = 200


def _is_keep_old(text: str) -> bool:
    return text.strip() in ("", "-")


@admin_only
async def list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    household_id = update.effective_chat.id
    conn = context.application.bot_data["db"]
    try:
        rows = task_repo.get_all_tasks(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load tasks: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách. Vui lòng thử lại sau."
        )
        return

    if not rows:
        await update.effective_message.reply_text(
            "Chưa có công việc nào. Dùng /add để thêm."
        )
        return

    today = date.today()
    lines = [f"📋 <b>Danh sách công việc bảo trì</b> ({len(rows)} công việc):\n"]
    for i, row in enumerate(rows, 1):
        try:
            due_date = date.fromisoformat(row["next_due_date"])
            delta = (due_date - today).days
            if delta < 0:
                status = f"⚠️ Quá hạn {abs(delta)} ngày"
            elif delta == 0:
                status = "📅 Đến hạn hôm nay"
            else:
                status = f"còn {delta} ngày"
            date_display = due_date.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            logger.warning("Task id=%s has invalid next_due_date: %r", row["id"], row["next_due_date"])
            status = "⚠️ Ngày không hợp lệ"
            date_display = html.escape(str(row["next_due_date"]))
        lines.append(
            f"{i}. <b>{html.escape(row['name'])}</b> — "
            f"{date_display} ({status})"
        )

    try:
        await update.effective_message.reply_text(
            "\n".join(lines),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send task list: %s", exc)
        await update.effective_message.reply_text(
            "Không thể gửi danh sách. Vui lòng thử lại sau."
        )


@admin_only
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["household_id"] = update.effective_chat.id
    await update.effective_message.reply_text(
        "Tên công việc là gì? (ví dụ: Thay lõi lọc nước)"
    )
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if not name:
        await update.effective_message.reply_text(
            "Tên không được để trống. Nhập lại tên công việc:"
        )
        return ASK_NAME
    if len(name) > MAX_TASK_NAME_LEN:
        await update.effective_message.reply_text(
            f"Tên quá dài (tối đa {MAX_TASK_NAME_LEN} ký tự). Nhập lại:"
        )
        return ASK_NAME
    context.user_data["task_name"] = name
    await update.effective_message.reply_text(
        "Chu kỳ lặp lại? (ví dụ: 30 ngày, 90 ngày, 180 ngày)"
    )
    return ASK_CYCLE


async def receive_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    match = re.match(r"(\d+)", text)
    cycle_days = int(match.group(1)) if match else 0
    if cycle_days <= 0:
        await update.effective_message.reply_text(
            "Chu kỳ phải là số nguyên dương (ví dụ: 30 hoặc 30 ngày). Nhập lại:"
        )
        return ASK_CYCLE
    context.user_data["cycle_days"] = cycle_days
    await update.effective_message.reply_text(
        "Ngày đến hạn tiếp theo? (định dạng DD/MM/YYYY)"
    )
    return ASK_DATE


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    try:
        due_date = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        await update.effective_message.reply_text(
            "Ngày không hợp lệ. Vui lòng nhập theo định dạng DD/MM/YYYY "
            "(ví dụ: 25/06/2026):"
        )
        return ASK_DATE

    name = context.user_data.get("task_name")
    cycle_days = context.user_data.get("cycle_days")
    household_id = context.user_data.get("household_id", 0)
    if not name or cycle_days is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /add."
        )
        return ConversationHandler.END

    conn = context.application.bot_data["db"]
    try:
        task_repo.create_task(conn, name, cycle_days, due_date.isoformat(), household_id)
    except Exception as exc:
        logger.error("Failed to save task: %s", exc)
        await update.effective_message.reply_text(
            "Không thể lưu Task. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    reminder_date = due_date - timedelta(days=1)
    await update.effective_message.reply_text(
        f"✅ Đã thêm: <b>{html.escape(name)}</b> — "
        f"đến hạn {due_date.strftime('%d/%m/%Y')}, "
        f"nhắc trước 1 ngày vào {reminder_date.strftime('%d/%m/%Y')}.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy. Task không được lưu.")
    return ConversationHandler.END


def build_add_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_CYCLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cycle)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )


# ── Edit conversation ────────────────────────────────────────────────────────

@admin_only
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = update.effective_chat.id
    context.user_data["household_id"] = household_id
    conn = context.application.bot_data["db"]
    try:
        rows = task_repo.get_all_tasks(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load tasks for edit: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    if not rows:
        await update.effective_message.reply_text(
            "Chưa có công việc nào để sửa. Dùng /add để thêm."
        )
        return ConversationHandler.END

    today = date.today()
    lines = ["📋 Chọn số thứ tự Task muốn sửa:\n"]
    for i, row in enumerate(rows, 1):
        try:
            due_date = date.fromisoformat(row["next_due_date"])
            delta = (due_date - today).days
            if delta < 0:
                status = f"⚠️ Quá hạn {abs(delta)} ngày"
            elif delta == 0:
                status = "📅 Đến hạn hôm nay"
            else:
                status = f"còn {delta} ngày"
            date_display = due_date.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            status = "⚠️ Ngày không hợp lệ"
            date_display = html.escape(str(row["next_due_date"]))
        lines.append(f"{i}. <b>{html.escape(row['name'])}</b> — {date_display} ({status})")
    lines.append("\n(hoặc /cancel để hủy)")

    context.user_data["edit_task_ids"] = [row["id"] for row in rows]
    try:
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send edit list: %s", exc)
        await update.effective_message.reply_text(
            "Không thể gửi danh sách. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    return EDIT_SELECT


async def receive_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task_ids = context.user_data.get("edit_task_ids", [])
    if not text.isdigit() or not task_ids:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(task_ids)}:"
        )
        return EDIT_SELECT

    choice = int(text)
    if choice < 1 or choice > len(task_ids):
        await update.effective_message.reply_text(
            f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(task_ids)}:"
        )
        return EDIT_SELECT

    task_id = task_ids[choice - 1]
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        task = task_repo.get_task_by_id(conn, task_id, household_id)
    except Exception as exc:
        logger.error("Failed to fetch task: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải Task. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    if task is None:
        await update.effective_message.reply_text(
            "Task không còn tồn tại. Vui lòng bắt đầu lại."
        )
        return ConversationHandler.END

    context.user_data["edit_task"] = dict(task)
    await update.effective_message.reply_text(
        f"Tên hiện tại: <b>{html.escape(task['name'])}</b>.\n"
        f"Nhập tên mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_NAME


async def receive_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("edit_task")
    if task is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /edit."
        )
        return ConversationHandler.END

    if _is_keep_old(text):
        new_name = task["name"]
    else:
        if len(text) > MAX_TASK_NAME_LEN:
            await update.effective_message.reply_text(
                f"Tên quá dài (tối đa {MAX_TASK_NAME_LEN} ký tự). Nhập lại:"
            )
            return EDIT_NAME
        new_name = text

    context.user_data["edit_name"] = new_name
    await update.effective_message.reply_text(
        f"Chu kỳ hiện tại: <b>{task['cycle_days']} ngày</b>.\n"
        f"Nhập chu kỳ mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_CYCLE


async def receive_edit_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("edit_task")
    if task is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /edit."
        )
        return ConversationHandler.END

    if _is_keep_old(text):
        new_cycle = task["cycle_days"]
    else:
        match = re.match(r"(\d+)", text)
        new_cycle = int(match.group(1)) if match else 0
        if new_cycle <= 0:
            await update.effective_message.reply_text(
                "Chu kỳ phải là số nguyên dương. Nhập lại:"
            )
            return EDIT_CYCLE

    context.user_data["edit_cycle"] = new_cycle
    try:
        _due_disp = date.fromisoformat(task["next_due_date"]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        _due_disp = html.escape(str(task["next_due_date"]))
    await update.effective_message.reply_text(
        f"Ngày đến hạn hiện tại: <b>{_due_disp}</b>.\n"
        f"Nhập ngày mới theo định dạng DD/MM/YYYY (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_DATE


async def receive_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("edit_task")
    new_name = context.user_data.get("edit_name")
    new_cycle = context.user_data.get("edit_cycle")
    household_id = context.user_data.get("household_id", 0)
    if task is None or new_name is None or new_cycle is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /edit."
        )
        return ConversationHandler.END

    if _is_keep_old(text):
        new_date_str = task["next_due_date"]
        try:
            due_date = date.fromisoformat(new_date_str)
        except (ValueError, TypeError):
            await update.effective_message.reply_text(
                "Ngày lưu trữ không hợp lệ. Vui lòng nhập ngày mới theo định dạng DD/MM/YYYY:"
            )
            return EDIT_DATE
    else:
        try:
            due_date = datetime.strptime(text, "%d/%m/%Y").date()
            new_date_str = due_date.isoformat()
        except ValueError:
            await update.effective_message.reply_text(
                "Ngày không hợp lệ. Vui lòng nhập theo định dạng DD/MM/YYYY "
                "(hoặc '-' để giữ nguyên):"
            )
            return EDIT_DATE

    conn = context.application.bot_data["db"]
    try:
        task_repo.update_task(conn, task["id"], new_name, new_cycle, new_date_str, household_id)
    except Exception as exc:
        logger.error("Failed to update task: %s", exc)
        await update.effective_message.reply_text(
            "Không thể cập nhật Task. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    reminder_date = due_date - timedelta(days=1)
    try:
        await update.effective_message.reply_text(
            f"✅ Đã cập nhật: <b>{html.escape(new_name)}</b> — "
            f"đến hạn {due_date.strftime('%d/%m/%Y')}, "
            f"nhắc trước 1 ngày vào {reminder_date.strftime('%d/%m/%Y')}.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send update confirmation: %s", exc)
    return ConversationHandler.END


async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy sửa.")
    return ConversationHandler.END


def build_edit_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_select)],
            EDIT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_name)],
            EDIT_CYCLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_cycle)],
            EDIT_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_date)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )


# ── Delete conversation ──────────────────────────────────────────────────────

@admin_only
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    household_id = update.effective_chat.id
    context.user_data["household_id"] = household_id
    conn = context.application.bot_data["db"]
    try:
        rows = task_repo.get_all_tasks(conn, household_id)
    except Exception as exc:
        logger.error("Failed to load tasks for delete: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    if not rows:
        await update.effective_message.reply_text("Chưa có công việc nào để xóa.")
        return ConversationHandler.END

    today = date.today()
    lines = ["📋 Chọn số thứ tự Task muốn xóa:\n"]
    for i, row in enumerate(rows, 1):
        try:
            due_date = date.fromisoformat(row["next_due_date"])
            delta = (due_date - today).days
            if delta < 0:
                status = f"⚠️ Quá hạn {abs(delta)} ngày"
            elif delta == 0:
                status = "📅 Đến hạn hôm nay"
            else:
                status = f"còn {delta} ngày"
            date_display = due_date.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            status = "⚠️ Ngày không hợp lệ"
            date_display = html.escape(str(row["next_due_date"]))
        lines.append(f"{i}. <b>{html.escape(row['name'])}</b> — {date_display} ({status})")
    lines.append("\n(hoặc /cancel để hủy)")

    context.user_data["delete_task_ids"] = [row["id"] for row in rows]
    try:
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send delete list: %s", exc)
        await update.effective_message.reply_text(
            "Không thể gửi danh sách. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    return DELETE_SELECT


async def receive_delete_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task_ids = context.user_data.get("delete_task_ids", [])
    if not text.isdigit() or not task_ids:
        await update.effective_message.reply_text(
            f"Vui lòng nhập số từ 1 đến {len(task_ids)}:"
        )
        return DELETE_SELECT

    choice = int(text)
    if choice < 1 or choice > len(task_ids):
        await update.effective_message.reply_text(
            f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(task_ids)}:"
        )
        return DELETE_SELECT

    task_id = task_ids[choice - 1]
    household_id = context.user_data.get("household_id", 0)
    conn = context.application.bot_data["db"]
    try:
        task = task_repo.get_task_by_id(conn, task_id, household_id)
    except Exception as exc:
        logger.error("Failed to fetch task: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải Task. Vui lòng thử lại sau."
        )
        return ConversationHandler.END

    if task is None:
        await update.effective_message.reply_text(
            "Task không còn tồn tại. Vui lòng bắt đầu lại."
        )
        return ConversationHandler.END

    context.user_data["delete_task"] = dict(task)
    try:
        await update.effective_message.reply_text(
            f"Bạn có chắc muốn xóa <b>{html.escape(task['name'])}</b>? "
            f"Trả lời 'Có' để xác nhận hoặc 'Không' để hủy.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send delete confirm: %s", exc)
        return ConversationHandler.END
    return DELETE_CONFIRM


async def receive_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("delete_task")
    household_id = context.user_data.get("household_id", 0)
    if task is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /delete."
        )
        return ConversationHandler.END

    if text.lower() == "có":
        conn = context.application.bot_data["db"]
        try:
            task_repo.delete_task(conn, task["id"], household_id)
        except Exception as exc:
            logger.error("Failed to delete task: %s", exc)
            await update.effective_message.reply_text(
                "Không thể xóa Task. Vui lòng thử lại sau."
            )
            return ConversationHandler.END
        try:
            await update.effective_message.reply_text(
                f"✅ Đã xóa: <b>{html.escape(task['name'])}</b>",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.error("Failed to send delete confirmation: %s", exc)
    else:
        await update.effective_message.reply_text("Đã hủy xóa.")
    return ConversationHandler.END


async def delete_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy xóa.")
    return ConversationHandler.END


def build_delete_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={
            DELETE_SELECT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_select)],
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_confirm)],
        },
        fallbacks=[CommandHandler("cancel", delete_cancel)],
    )
