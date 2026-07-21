import asyncio
import html
import logging
import os
from datetime import date, timedelta

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


async def _typing(update: Update, seconds: float = 1.5) -> None:
    await update.effective_chat.send_action("typing")
    await asyncio.sleep(seconds)


async def demo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scripted investor demo walkthrough — /demo"""
    conn = context.application.bot_data["db"]
    today = date.today()
    chat_id = update.effective_chat.id

    # ── Gather real stats ──────────────────────────────────────────────
    households = conn.execute(
        "SELECT COUNT(DISTINCT household_id) FROM TASK WHERE household_id != 0"
    ).fetchone()[0]
    total_tasks = conn.execute("SELECT COUNT(*) FROM TASK").fetchone()[0]
    overdue = conn.execute(
        "SELECT COUNT(*) FROM TASK WHERE next_due_date < ?", (today.isoformat(),)
    ).fetchone()[0]
    repairmen = conn.execute("SELECT COUNT(*) FROM REPAIRMAN").fetchone()[0]
    incidents = conn.execute("SELECT COUNT(*) FROM INCIDENT").fetchone()[0]
    members = conn.execute("SELECT COUNT(*) FROM MEMBER").fetchone()[0]

    score = max(0, 100 - overdue * 8 - min(incidents, 5) * 3)
    score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"

    # Sample repairman from DB (for realistic AI response)
    sample_repairman = conn.execute(
        "SELECT name, phone, service_type FROM REPAIRMAN WHERE service_type LIKE '%máy lạnh%' LIMIT 1"
    ).fetchone()
    if not sample_repairman:
        sample_repairman = conn.execute(
            "SELECT name, phone, service_type FROM REPAIRMAN LIMIT 1"
        ).fetchone()

    due_date_example = (today + timedelta(days=30)).strftime("%d/%m/%Y")

    # ── Step 1: Intro ──────────────────────────────────────────────────
    await _typing(update, 1.0)
    await update.effective_message.reply_text(
        "🏠 <b>HomeKeeper Agent — Demo</b>\n\n"
        "Nền tảng quản lý bảo trì nhà thông minh.\n"
        "AI-Powered · Multi-tenant · Telegram-native · Zero app install\n\n"
        "<i>Demo sẽ chạy tự động, mỗi bước cách nhau vài giây...</i>",
        parse_mode="HTML",
    )

    # ── Step 2: Platform stats ─────────────────────────────────────────
    await _typing(update, 2.0)
    await update.effective_message.reply_text(
        "📊 <b>Platform Overview — Live Data</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🏘️  Hộ gia đình đang dùng: <b>{households}</b>\n"
        f"📋  Công việc đang theo dõi: <b>{total_tasks}</b>\n"
        f"🔧  Thợ sửa chữa trong hệ thống: <b>{repairmen}</b>\n"
        f"👥  Thành viên gia đình: <b>{members}</b>\n"
        f"🚨  Sự cố đã xử lý: <b>{incidents}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{score_emoji} <b>Health Score: {score}/100</b>\n\n"
        "<i>↑ Data thật, cập nhật real-time từ tất cả hộ gia đình</i>",
        parse_mode="HTML",
    )

    # ── Step 3: AI photo analysis (scripted but realistic) ─────────────
    await _typing(update, 2.5)
    repairman_line = ""
    if sample_repairman:
        repairman_line = (
            f"\n🔧 <b>Thợ gợi ý tự động:</b>\n"
            f"  👤 <b>{html.escape(sample_repairman[0])}</b> "
            f"— 📞 {sample_repairman[1]} ({sample_repairman[2]})"
        )
    await update.effective_message.reply_text(
        "📸 <b>Tính năng 1: AI Phân tích ảnh</b>\n\n"
        "<i>Người dùng chụp ảnh điều hòa hỏng và gửi lên → Bot phân tích:</i>\n\n"
        "🏠 <b>Kết quả phân tích ảnh</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 <b>Vấn đề:</b> Máy lạnh không làm lạnh, lọc bẩn hoặc thiếu gas\n"
        "🟠 <b>Mức độ:</b> Trung bình\n"
        "💡 <b>Khuyến nghị:</b> Vệ sinh lọc, kiểm tra áp suất gas, gọi thợ nếu vẫn không cải thiện"
        f"{repairman_line}\n\n"
        "<i>✦ Dùng OpenRouter Vision AI · Phân tích trong &lt;5 giây</i>",
        parse_mode="HTML",
    )

    # ── Step 4: NLP demo ──────────────────────────────────────────────
    await _typing(update, 2.5)
    await update.effective_message.reply_text(
        "💬 <b>Tính năng 2: Ngôn ngữ tự nhiên</b>\n\n"
        "Người dùng nhắn:\n"
        "  <i>\"nhắc tôi vệ sinh máy lạnh sau 30 ngày\"</i>\n\n"
        "Bot tự động xử lý:\n"
        f"  ✅ Tạo task: <b>Vệ sinh máy lạnh</b>\n"
        f"  📅 Ngày nhắc: <b>{due_date_example}</b>\n"
        f"  🔔 Reminder tự động gửi đúng ngày cho cả nhà\n\n"
        "Hoặc: <i>\"điều hòa phòng khách không mát\"</i>\n"
        f"  → Bot tìm thợ máy lạnh phù hợp và gợi ý ngay\n\n"
        "<i>✦ Dùng Groq llama-3.3-70b · Không cần form, không cần app</i>",
        parse_mode="HTML",
    )

    # ── Step 5: Multi-tenant pitch ────────────────────────────────────
    await _typing(update, 2.0)
    await update.effective_message.reply_text(
        "👥 <b>Tính năng 3: Multi-tenant tự động</b>\n\n"
        "  Mỗi group Telegram = 1 hộ gia đình riêng biệt\n"
        "  Dữ liệu hoàn toàn tách biệt giữa các hộ\n"
        "  Không cần đăng ký, không cần cài app\n\n"
        "<b>Scale:</b>\n"
        "  1 bot → vô số hộ gia đình\n"
        "  1 server → toàn bộ fleet\n"
        "  Chi phí infra tăng tuyến tính theo usage\n\n"
        "<i>✦ Phù hợp B2C (cá nhân) và B2B (property management, chung cư)</i>",
        parse_mode="HTML",
    )

    # ── Step 6: CTA ───────────────────────────────────────────────────
    await _typing(update, 1.5)
    dashboard_url = os.environ.get("DASHBOARD_URL", "Railway URL của bạn")
    await update.effective_message.reply_text(
        "🚀 <b>HomeKeeper Agent</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Stack:</b> Python · FastAPI · Telegram Bot API\n"
        "<b>AI:</b> Groq llama-3.3-70b + OpenRouter Vision\n"
        "<b>Deploy:</b> Railway · SQLite · Zero DevOps\n\n"
        f"🌐 <b>Dashboard:</b> {html.escape(dashboard_url)}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Thử ngay: gửi ảnh bất kỳ thiết bị trong nhà ↑",
        parse_mode="HTML",
    )


def build_demo_handlers() -> list:
    return [
        CommandHandler("remind", remind_handler),
        CommandHandler("status", status_handler),
        CommandHandler("demo", demo_handler),
    ]
