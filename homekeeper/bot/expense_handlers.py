import html
import logging

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from homekeeper.db import expense_repo

logger = logging.getLogger(__name__)


async def expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/expense [amount] — log an expense or show monthly summary."""
    household_id = update.effective_chat.id if update.effective_chat else 0
    conn = context.application.bot_data["db"]

    # /expense <amount> — log new expense
    if context.args:
        raw = context.args[0].replace(".", "").replace(",", "")
        try:
            amount = int(raw)
        except ValueError:
            await update.effective_message.reply_text(
                "Số tiền không hợp lệ. Ví dụ: /expense 500000"
            )
            return
        if amount <= 0:
            await update.effective_message.reply_text("Số tiền phải lớn hơn 0.")
            return

        note = " ".join(context.args[1:])[:200] if len(context.args) > 1 else None
        try:
            expense_repo.create_expense(conn, amount=amount, household_id=household_id, note=note)
        except Exception as exc:
            logger.error("Failed to save expense: %s", exc)
            await update.effective_message.reply_text("Không thể ghi chi phí. Vui lòng thử lại.")
            return

        formatted = f"{amount:,}".replace(",", ".")
        note_str = f" — {html.escape(note)}" if note else ""
        await update.effective_message.reply_text(
            f"💰 Đã ghi chi phí: <b>{formatted} VND</b>{note_str}",
            parse_mode="HTML",
        )
        return

    # /expense — show monthly summary
    rows = expense_repo.get_monthly_summary(conn, household_id)
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có chi phí nào được ghi.\n"
            "Dùng <code>/expense 500000</code> để thêm.",
            parse_mode="HTML",
        )
        return

    # Parse rows in chronological order (DB returns newest first)
    months = []
    total_all = 0
    for row in reversed(rows):
        month_str = row[0]   # YYYY-MM
        total = row[1] or 0
        cnt = row[2] or 0
        total_all += total
        y, m = month_str.split("-")
        months.append({"label": f"{m}/{y}", "total": total, "cnt": cnt})

    # Build text bar chart
    max_total = max(mo["total"] for mo in months) or 1
    bar_width = 12
    chart_lines = ["💰 <b>Chi phí bảo trì 6 tháng</b>\n"]
    for mo in months:
        fill = round(mo["total"] / max_total * bar_width)
        bar = "█" * fill + "░" * (bar_width - fill)
        amt = f"{mo['total']:,}".replace(",", ".")
        chart_lines.append(f"<code>{mo['label']}  {bar}  {amt}đ</code>")

    grand = f"{total_all:,}".replace(",", ".")
    avg = f"{total_all // len(months):,}".replace(",", ".") if months else "0"
    chart_lines.append(f"\n📊 Tổng: <b>{grand} VND</b>  |  TB/tháng: {avg} VND")
    chart_lines.append(f"<i>({sum(mo['cnt'] for mo in months)} lần ghi nhận)</i>")
    await update.effective_message.reply_text("\n".join(chart_lines), parse_mode="HTML")


def build_expense_handlers() -> list:
    return [CommandHandler("expense", expense_handler)]
