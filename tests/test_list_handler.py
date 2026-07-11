"""Tests for list_handler in task_handlers (Story 1.3)."""

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homekeeper.bot.task_handlers import list_handler
from homekeeper.db.task_repo import create_task


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def _make_update_context(conn):
    """Build minimal mock Update + Context objects."""
    message = MagicMock()
    message.reply_text = AsyncMock()

    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = message

    application = MagicMock()
    application.bot_data = {"db": conn}

    context = MagicMock()
    context.application = application

    return update, context


@pytest.fixture(autouse=True)
def patch_admin():
    """Bypass @admin_only by patching the env var and effective_user id."""
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield


@pytest.mark.asyncio
async def test_list_handler_empty_db(conn):
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    update.effective_message.reply_text.assert_called_once()
    call_args = update.effective_message.reply_text.call_args
    assert "Chưa có công việc nào" in call_args[0][0]


@pytest.mark.asyncio
async def test_list_handler_single_future_task(conn):
    create_task(conn, "Thay lõi lọc nước", 90, "2099-12-31")
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    call_args = update.effective_message.reply_text.call_args
    msg = call_args[0][0]
    assert "Thay lõi lọc nước" in msg
    assert "còn" in msg
    assert call_args[1].get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_list_handler_overdue_task(conn):
    create_task(conn, "Vệ sinh máy lọc", 30, "2020-01-01")
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "⚠️ Quá hạn" in msg


@pytest.mark.asyncio
async def test_list_handler_due_today(conn):
    today_str = date.today().isoformat()
    create_task(conn, "Task hôm nay", 7, today_str)
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Đến hạn hôm nay" in msg


@pytest.mark.asyncio
async def test_list_handler_multiple_tasks_numbered(conn):
    create_task(conn, "Task B", 30, "2099-08-01")
    create_task(conn, "Task A", 30, "2099-07-01")
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    # Task A should appear first (earlier date)
    assert msg.index("Task A") < msg.index("Task B")
    assert "1." in msg
    assert "2." in msg


@pytest.mark.asyncio
async def test_list_handler_html_escapes_task_name(conn):
    create_task(conn, "Task <script>alert(1)</script>", 30, "2099-07-01")
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg


@pytest.mark.asyncio
async def test_list_handler_db_error_replies_gracefully(conn):
    update, context = _make_update_context(conn)
    # Replace db with a broken connection
    context.application.bot_data = {"db": None}
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Không thể tải" in msg


@pytest.mark.asyncio
async def test_list_handler_malformed_date_shows_invalid_marker(conn):
    # Insert a row with a datetime string instead of a date string
    conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at) VALUES (?, ?, ?, ?)",
        ("Task Bad Date", 30, "2026-07-01T00:00:00", "2026-06-28T00:00:00"),
    )
    conn.commit()
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    # Handler must not crash; should show an invalid-date marker
    assert "Task Bad Date" in msg
    assert "Ngày không hợp lệ" in msg


@pytest.mark.asyncio
async def test_list_handler_same_date_stable_order(conn):
    create_task(conn, "Task X", 30, "2099-07-01")
    create_task(conn, "Task Y", 30, "2099-07-01")
    update, context = _make_update_context(conn)
    await list_handler(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    # Task X inserted first → lower id → must appear as item 1
    assert msg.index("Task X") < msg.index("Task Y")
