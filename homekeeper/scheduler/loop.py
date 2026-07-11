import html
import logging
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from homekeeper.db import member_repo, reminder_log_repo, task_repo
from homekeeper.db.connection import open_db
from homekeeper.domain.overdue import days_overdue, is_overdue
from homekeeper.scheduler import sender

_VN_TZ = timezone(timedelta(hours=7))

logger = logging.getLogger(__name__)


def _task_unchanged(conn, task_id: int, expected_due_date: str) -> bool:
    """Re-read Task to confirm next_due_date hasn't changed (AD-8 guard).

    Call before each REMINDER_LOG write in Stories 2.2+. Returns False if task
    was deleted or its due date changed since the send decision was made.
    """
    row = task_repo.get_task_by_id(conn, task_id)
    if row is None:
        return False
    return row["next_due_date"] == expected_due_date


def _check_d1(conn, task) -> None:
    """Send D-1 reminder if not yet sent for this task's current due-date cycle."""
    task_id = task["id"]
    due_date = task["next_due_date"]  # YYYY-MM-DD

    # D-1 is expected to fire on due_date - 1 day
    reminder_date = (date.fromisoformat(due_date) - timedelta(days=1)).isoformat()

    # Idempotency gate: skip if already sent for this cycle
    if reminder_log_repo.already_sent(conn, task_id, "D-1", reminder_date):
        return

    # AD-8 guard: re-read task to confirm due_date hasn't changed since we decided to send
    if not _task_unchanged(conn, task_id, due_date):
        return

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    text = f"🔔 Nhắc nhở: <b>{html.escape(task['name'])}</b> đến hạn vào ngày mai ({vn_date_display})."

    # Send to admin — if this fails, don't log (retry next tick)
    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, text)
    except Exception as exc:
        logger.error("Failed to send D-1 to admin for task %d: %s", task_id, exc)
        return

    # Log the send — AFTER admin succeeds, BEFORE members (members are best-effort)
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "D-1", sent_at)
    logger.info("D-1 reminder sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    # Send to members (best-effort — failure does not affect REMINDER_LOG or other members)
    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning(
                "Failed to send D-1 to member %d: %s", member["telegram_user_id"], exc
            )


def _check_d0(conn, task) -> None:
    """Send D-0 reminder if not yet sent for this task's current due-date cycle."""
    task_id = task["id"]
    due_date = task["next_due_date"]  # YYYY-MM-DD

    # D-0 fires on the due date itself — reminder_date == due_date
    reminder_date = due_date

    if reminder_log_repo.any_sent_on_date(conn, task_id, reminder_date):
        return

    if not _task_unchanged(conn, task_id, due_date):
        return

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    text = f"📅 Đến hạn hôm nay: <b>{html.escape(task['name'])}</b> ({vn_date_display})."

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
        logger.error("Failed to send D-0 to admin for task %d: %s", task_id, exc)
        return

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "D-0", sent_at)
    logger.info("D-0 reminder sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning(
                "Failed to send D-0 to member %d: %s", member["telegram_user_id"], exc
            )


def _check_overdue(conn, task) -> None:
    """Send hourly overdue reminder if 1+ hour since last overdue send."""
    task_id = task["id"]
    due_date = task["next_due_date"]

    if not is_overdue(task):
        return

    latest_overdue = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    latest_catchup = reminder_log_repo.get_latest_sent_at(conn, task_id, "catchup")
    candidates = [t for t in [latest_overdue, latest_catchup] if t is not None]
    latest_sent_at = max(candidates) if candidates else None
    if latest_sent_at is not None:
        sent_dt = datetime.fromisoformat(latest_sent_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - sent_dt < timedelta(hours=1):
            return

    if not _task_unchanged(conn, task_id, due_date):
        return

    n = days_overdue(task)
    admin_text = f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> đã trễ {n} ngày. Bạn đã xử lý chưa?"
    member_text = f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> đã trễ {n} ngày."
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done:{task_id}:{due_date}"),
            InlineKeyboardButton("⏭ Bỏ qua lần này", callback_data=f"skip:{task_id}:{due_date}"),
        ]
    ])

    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, admin_text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Failed to send overdue to admin for task %d: %s", task_id, exc)
        return

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "overdue", sent_at)
    logger.info(
        "Overdue reminder sent: task_id=%d name=%r due=%s days_overdue=%d",
        task_id, task["name"], due_date, n,
    )

    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], member_text)
        except Exception as exc:
            logger.warning(
                "Failed to send overdue to member %d: %s", member["telegram_user_id"], exc
            )


def _tick(conn, _now=None) -> None:
    """One scheduler tick. _now is injectable for testing (defaults to VN local time)."""
    logger.debug("Scheduler tick")
    if _now is None:
        _now = datetime.now(_VN_TZ)
    if _now.hour < 8:
        return
    tasks = task_repo.get_all_tasks(conn)
    tomorrow = _now.date() + timedelta(days=1)
    today = _now.date()
    for task in tasks:
        try:
            due = date.fromisoformat(task["next_due_date"])
        except (ValueError, TypeError):
            logger.warning("Task %d has invalid next_due_date: %r", task["id"], task["next_due_date"])
            continue
        if due == tomorrow:
            _check_d1(conn, task)
        if due == today:
            _check_d0(conn, task)
        if due < today:
            _check_overdue(conn, task)


def _run_loop() -> None:
    """Scheduler thread body: opens own DB connection, polls every 60 seconds."""
    try:
        conn = open_db()
    except Exception as exc:
        logger.error("Scheduler failed to open DB: %s — thread exiting", exc)
        return
    logger.info("Scheduler started — polling every 60 seconds")
    while True:
        try:
            _tick(conn)
        except Exception as exc:
            logger.error("Scheduler tick error: %s", exc)
        time.sleep(60)


def start_scheduler() -> threading.Thread:
    """Spawn scheduler as a daemon thread. Returns the started thread."""
    t = threading.Thread(target=_run_loop, name="scheduler", daemon=True)
    t.start()
    return t
