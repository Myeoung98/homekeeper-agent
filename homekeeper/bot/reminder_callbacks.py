import html
import logging
import os
from datetime import date, datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from homekeeper.db import reminder_log_repo, task_repo

logger = logging.getLogger(__name__)

CALLBACK_PATTERN = r'^(done|skip):\d+:\d{4}-\d{2}-\d{2}$'


async def handle_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle done/skip button presses from D-0 reminder messages.

    callback_data format: "done:{task_id}:{due_date}" or "skip:{task_id}:{due_date}"
    Single writer for TASK.next_due_date (AD-8).
    """
    query = update.callback_query
    # Acknowledge immediately — clears Telegram spinner regardless of outcome
    await query.answer()

    # Guard: no message to reply to (deleted message or channel post)
    if query.message is None:
        return

    # Admin-only guard: non-admin gets spinner cleared but no action
    admin_id_str = os.environ.get("ADMIN_USER_ID", "")
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        logger.error("ADMIN_USER_ID is not a valid integer: %r", admin_id_str)
        return

    if update.effective_user is None or update.effective_user.id != admin_id:
        return

    # Parse callback_data
    data = query.data
    action, task_id_str, due_date_str = data.split(":", 2)
    task_id = int(task_id_str)

    # Derive household_id from the chat where the button was pressed
    household_id = update.effective_chat.id if update.effective_chat else 0

    conn = context.bot_data["db"]
    task = task_repo.get_task_by_id(conn, task_id, household_id)

    # Stale check: task deleted or already advanced to next cycle
    if task is None or task["next_due_date"] != due_date_str:
        await query.message.reply_text(
            "Reminder này đã hết hiệu lực. Xem /list để biết trạng thái hiện tại."
        )
        return

    # Compute new due date
    new_due_date = (date.fromisoformat(due_date_str) + timedelta(days=task["cycle_days"])).isoformat()
    confirmed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_due_display = date.fromisoformat(new_due_date).strftime("%d/%m/%Y")

    # DB: mark reminder confirmed, advance task due date
    rowcount = reminder_log_repo.confirm_reminder(conn, task_id, "D-0", due_date_str, confirmed_at)
    if rowcount == 0:
        logger.warning(
            "confirm_reminder matched 0 rows for task_id=%d due=%s — proceeding with advance",
            task_id, due_date_str,
        )
    task_repo.advance_next_due_date(conn, task_id, new_due_date, household_id)
    logger.info(
        "Reminder callback %s: task_id=%d name=%r new_due=%s",
        action, task_id, task["name"], new_due_date,
    )

    # Reply to chat
    task_name = html.escape(task["name"])
    if action == "done":
        text = f"✅ Đã ghi nhận: <b>{task_name}</b> hoàn thành. Hạn tiếp theo: {new_due_display}."
    else:
        text = f"⏭ Đã bỏ qua. Hạn tiếp theo: {new_due_display}."

    await query.message.reply_text(text, parse_mode="HTML")
