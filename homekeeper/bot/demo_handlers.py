import html
import logging
import os
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes

from homekeeper.bot import admin_only
from homekeeper.db import member_repo, task_repo

logger = logging.getLogger(__name__)


@admin_only
async def remind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a task's D-0 reminder immediately — for demo/testing purposes."""
    household_id = update.effective_chat.id
    conn = context.application.bot_data["db"]

    if not context.args:
        tasks = task_repo.get_all_tasks(conn, household_id)
        if not tasks:
            await update.effective_message.reply_text("Chưa có task nào. Dùng /add để tạo task.")
            return
        lines = ["Chọn task để gửi reminder:\n"]
        for t in tasks[:10]:
            due = t["next_due_date"]
            lines.append(f"  /remind {t['id']} — <b>{html.escape(t['name'])}</b> (hạn: {due})")
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("Dùng: /remind <task_id>")
        return

    task = task_repo.get_task_by_id(conn, task_id, household_id)
    if task is None:
        await update.effective_message.reply_text(f"Không tìm thấy task ID {task_id}.")
        return

    due_date = task["next_due_date"]
    vn_date = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    text = f"📅 Đến hạn hôm nay: <b>{html.escape(task['name'])}</b> ({vn_date})."
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done:{task_id}:{due_date}"),
        InlineKeyboardButton("⏭ Bỏ qua lần này", callback_data=f"skip:{task_id}:{due_date}"),
    ]])

    admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
    try:
        await context.bot.send_message(
            chat_id=admin_id, text=text, parse_mode="HTML", reply_markup=keyboard
        )
    except Exception as exc:
        await update.effective_message.reply_text(f"Lỗi gửi reminder: {exc}")
        return

    members = member_repo.get_all_members(conn, household_id)
    for member in members:
        try:
            await context.bot.send_message(
                chat_id=member["telegram_user_id"], text=text, parse_mode="HTML"
            )
        except Exception as exc:
            logger.warning("remind_handler: member %d failed: %s", member["telegram_user_id"], exc)

    member_note = f" + {len(members)} thành viên" if members else ""
    await update.effective_message.reply_text(
        f"✅ Đã gửi reminder cho <b>{html.escape(task['name'])}</b> đến admin{member_note}.",
        parse_mode="HTML",
    )


@admin_only
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show a system dashboard — tasks, members, repairmen, incidents."""
    household_id = update.effective_chat.id
    conn = context.application.bot_data["db"]
    today = date.today()

    tasks = task_repo.get_all_tasks(conn, household_id)
    overdue = [t for t in tasks if date.fromisoformat(t["next_due_date"]) < today]
    due_today = [t for t in tasks if date.fromisoformat(t["next_due_date"]) == today]
    upcoming = [t for t in tasks if date.fromisoformat(t["next_due_date"]) > today]

    members = member_repo.get_all_members(conn, household_id)

    repairman_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM REPAIRMAN WHERE household_id = ?", (household_id,)
    ).fetchone()["cnt"]
    incident_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM INCIDENT WHERE household_id = ?", (household_id,)
    ).fetchone()["cnt"]

    lines = [
        "📊 <b>HomeKeeper — Tổng quan hệ thống</b>\n",
        f"🗓 Hôm nay: {today.strftime('%d/%m/%Y')}\n",
        "━━━━━━━━━━━━━━━━━━━━",
        "📋 <b>CÔNG VIỆC BẢO TRÌ</b>",
        f"  Tổng số task: {len(tasks)}",
    ]

    if overdue:
        lines.append(f"  ⚠️ Quá hạn: {len(overdue)}")
        for t in overdue[:3]:
            days = (today - date.fromisoformat(t["next_due_date"])).days
            lines.append(f"    • {html.escape(t['name'])} (trễ {days} ngày)")

    if due_today:
        lines.append(f"  🔴 Đến hạn hôm nay: {len(due_today)}")
        for t in due_today:
            lines.append(f"    • {html.escape(t['name'])}")

    if upcoming:
        lines.append(f"  ✅ Sắp tới ({len(upcoming)} task):")
        for t in upcoming[:3]:
            due = date.fromisoformat(t["next_due_date"])
            days_left = (due - today).days
            lines.append(
                f"    • {html.escape(t['name'])} — {due.strftime('%d/%m/%Y')} ({days_left} ngày nữa)"
            )
        if len(upcoming) > 3:
            lines.append(f"    ... và {len(upcoming) - 3} task khác")

    if not tasks:
        lines.append("  (Chưa có task nào — dùng /add để tạo)")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        "👥 <b>THÀNH VIÊN GIA ĐÌNH</b>",
    ]
    if members:
        for m in members:
            lines.append(f"  • {html.escape(m['name'] or '(không tên)')}")
    else:
        lines.append("  (Chưa có — dùng /member add)")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔧 Thợ sửa chữa: <b>{repairman_count}</b> người",
        f"🚨 Sự cố đã báo: <b>{incident_count}</b> lần",
        "━━━━━━━━━━━━━━━━━━━━",
        "\n💡 <i>Dùng /remind &lt;id&gt; để test gửi reminder ngay</i>",
    ]

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


def build_demo_handlers() -> list:
    return [
        CommandHandler("remind", remind_handler),
        CommandHandler("status", status_handler),
    ]
