import html
import logging
from datetime import date, timedelta

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from homekeeper.bot import admin_only
from homekeeper.db import expense_repo, incident_repo, task_repo

logger = logging.getLogger(__name__)


@admin_only
async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/report — monthly maintenance summary: tasks, expenses, incidents."""
    household_id = update.effective_chat.id if update.effective_chat else 0
    conn = context.application.bot_data["db"]

    today = date.today()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # ── Tasks ────────────────────────────────────────────────────────────
    all_tasks = task_repo.get_all_tasks(conn, household_id)
    overdue = [t for t in all_tasks if date.fromisoformat(t["next_due_date"]) < today]
    due_this_month = [
        t for t in all_tasks
        if first_of_month <= date.fromisoformat(t["next_due_date"]) < first_of_month.replace(month=today.month % 12 + 1, year=today.year + (1 if today.month == 12 else 0))
        if True
    ]

    # Count tasks confirmed done last month via REMINDER_LOG
    try:
        completed_last_month = conn.execute(
            "SELECT COUNT(*) FROM REMINDER_LOG "
            "WHERE confirmed_at IS NOT NULL "
            "AND confirmed_at >= ? AND confirmed_at < ?",
            (last_month_start.isoformat(), first_of_month.isoformat()),
        ).fetchone()[0]
    except Exception:
        completed_last_month = 0

    # ── Expenses ────────────────────────────────────────────────────────
    expense_rows = expense_repo.get_monthly_summary(conn, household_id)
    this_month_key = today.strftime("%Y-%m")
    last_month_key = last_month_end.strftime("%Y-%m")
    expense_map = {r[0]: (r[1] or 0, r[2] or 0) for r in expense_rows}
    this_month_exp, this_month_cnt = expense_map.get(this_month_key, (0, 0))
    last_month_exp, last_month_cnt = expense_map.get(last_month_key, (0, 0))

    # ── Incidents ───────────────────────────────────────────────────────
    try:
        incidents_this_month = conn.execute(
            "SELECT COUNT(*) FROM INCIDENT WHERE household_id = ? "
            "AND created_at >= ?",
            (household_id, first_of_month.isoformat()),
        ).fetchone()[0]
        incidents_last_month = conn.execute(
            "SELECT COUNT(*) FROM INCIDENT WHERE household_id = ? "
            "AND created_at >= ? AND created_at < ?",
            (household_id, last_month_start.isoformat(), first_of_month.isoformat()),
        ).fetchone()[0]
    except Exception:
        incidents_this_month = incidents_last_month = 0

    # ── Format ──────────────────────────────────────────────────────────
    def fmt(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    def trend(cur: int, prev: int) -> str:
        if prev == 0:
            return ""
        diff = cur - prev
        if diff > 0:
            return f" ▲{fmt(diff)}"
        if diff < 0:
            return f" ▼{fmt(abs(diff))}"
        return " ↔"

    vn_month = today.strftime("%m/%Y")
    vn_last = last_month_end.strftime("%m/%Y")

    lines = [
        f"📊 <b>Báo cáo bảo trì tháng {vn_month}</b>\n",
        "━━━━━━━━━━━━━━━━━━",
        "📋 <b>CÔNG VIỆC</b>",
        f"  Tổng lịch bảo trì: <b>{len(all_tasks)}</b>",
        f"  ⚠️ Đang quá hạn: <b>{len(overdue)}</b>",
        f"  ✅ Hoàn thành tháng {vn_last}: <b>{completed_last_month}</b>",
        "━━━━━━━━━━━━━━━━━━",
        "💰 <b>CHI PHÍ</b>",
        f"  Tháng này: <b>{fmt(this_month_exp)} VND</b> ({this_month_cnt} lần){trend(this_month_exp, last_month_exp)}",
        f"  Tháng trước ({vn_last}): {fmt(last_month_exp)} VND",
    ]

    if expense_rows:
        total_6m = sum(r[1] or 0 for r in expense_rows)
        avg_6m = total_6m // len(expense_rows)
        lines.append(f"  TB 6 tháng: {fmt(avg_6m)} VND/tháng")

    lines += [
        "━━━━━━━━━━━━━━━━━━",
        "🚨 <b>SỰ CỐ</b>",
        f"  Tháng này: <b>{incidents_this_month}</b>{trend(incidents_this_month, incidents_last_month)}",
        f"  Tháng trước: {incidents_last_month}",
    ]

    if overdue:
        lines += [
            "━━━━━━━━━━━━━━━━━━",
            "⚠️ <b>CẦN XỬ LÝ NGAY:</b>",
        ]
        for t in overdue[:5]:
            days = (today - date.fromisoformat(t["next_due_date"])).days
            lines.append(f"  • {html.escape(t['name'])} (trễ {days} ngày)")

    lines += [
        "━━━━━━━━━━━━━━━━━━",
        f"<i>Dùng /list để xem chi tiết · /expense để ghi chi phí</i>",
    ]

    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")


def build_report_handler():
    return CommandHandler("report", report_handler)
