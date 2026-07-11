import html
import logging
import os
from datetime import date, datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from homekeeper.db import member_repo, reminder_log_repo, task_repo
from homekeeper.scheduler import sender

logger = logging.getLogger(__name__)


def run_catchup(conn) -> None:
    """Send catch-up reminders for all missed tasks at startup.

    A "missed" task has next_due_date <= today with no REMINDER_LOG row on that date.
    Runs in the main thread before the scheduler daemon starts (AD-6).
    Logs type='catchup' — _check_d0 uses any_sent_on_date so it won't re-send.
    """
    today = date.today().isoformat()
    tasks = task_repo.get_all_tasks(conn)

    for task in tasks:
        due_date = task["next_due_date"]
        if due_date > today:
            continue

        if reminder_log_repo.any_sent_on_date(conn, task["id"], due_date):
            continue

        _send_catchup(conn, task, due_date, today)


def _send_catchup(conn, task, due_date: str, today: str) -> None:
    """Send one catch-up reminder and log it."""
    task_id = task["id"]

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    if due_date < today:
        days_late = (date.today() - date.fromisoformat(due_date)).days
        text = (
            f"⚡ Gửi bù (bot vừa khởi động lại): "
            f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> "
            f"đến hạn {vn_date_display} — đã trễ {days_late} ngày."
        )
    else:
        text = (
            f"⚡ Gửi bù (bot vừa khởi động lại): "
            f"📅 Đến hạn hôm nay: <b>{html.escape(task['name'])}</b> ({vn_date_display})."
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done:{task_id}:{due_date}"),
            InlineKeyboardButton("⏭ Bỏ qua lần này", callback_data=f"skip:{task_id}:{due_date}"),
        ]
    ])

    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Catch-up send failed for task %d: %s — skipping log", task_id, exc)
        return

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "catchup", sent_at)
    logger.info("Catch-up sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning("Catch-up member send failed %d: %s", member["telegram_user_id"], exc)
