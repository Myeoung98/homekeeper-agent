"""Tests for homekeeper/bot/reminder_callbacks.py (Story 2.4)."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

from homekeeper.db import reminder_log_repo, task_repo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def today_str() -> str:
    return date.today().isoformat()


def make_update(callback_data: str, user_id: int) -> tuple:
    """Return (update, query) mocks for a callback with given data and user_id."""
    query = MagicMock(spec=CallbackQuery)
    query.data = callback_data
    query.answer = AsyncMock()
    msg = MagicMock(spec=Message)
    msg.reply_text = AsyncMock()
    query.message = msg

    user = MagicMock(spec=User)
    user.id = user_id

    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    return update, query


def make_context(conn):
    context = MagicMock()
    context.bot_data = {"db": conn}
    return context


# ---------------------------------------------------------------------------
# Task 2.1 — Tests (RED phase)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_done_callback_answers_and_replies(conn, monkeypatch):
    """Done tap: query.answer() called, confirmation message sent."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "Clean AC", 30, due)
    # Simulate D-0 already sent
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, query = make_update(f"done:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    query.answer.assert_called_once()
    query.message.reply_text.assert_called_once()
    reply_text = query.message.reply_text.call_args[0][0]
    assert "Hoàn thành" in reply_text or "hoàn thành" in reply_text


@pytest.mark.asyncio
async def test_done_callback_advances_next_due_date(conn, monkeypatch):
    """Done tap: TASK.next_due_date advances by cycle_days."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, _ = make_update(f"done:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    row = task_repo.get_task_by_id(conn, task_id)
    expected = (date.fromisoformat(due) + timedelta(days=30)).isoformat()
    assert row["next_due_date"] == expected


@pytest.mark.asyncio
async def test_done_callback_sets_confirmed_at(conn, monkeypatch):
    """Done tap: REMINDER_LOG.confirmed_at is set."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, _ = make_update(f"done:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    row = conn.execute(
        "SELECT confirmed_at FROM REMINDER_LOG WHERE task_id=? AND type='D-0'", (task_id,)
    ).fetchone()
    assert row["confirmed_at"] is not None


@pytest.mark.asyncio
async def test_skip_callback_advances_next_due_date(conn, monkeypatch):
    """Skip tap: TASK.next_due_date advances by cycle_days (same as done)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 60, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, _ = make_update(f"skip:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    row = task_repo.get_task_by_id(conn, task_id)
    expected = (date.fromisoformat(due) + timedelta(days=60)).isoformat()
    assert row["next_due_date"] == expected


@pytest.mark.asyncio
async def test_skip_callback_reply_text_mentions_skip(conn, monkeypatch):
    """Skip tap: reply text mentions bỏ qua (skip)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, query = make_update(f"skip:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    reply_text = query.message.reply_text.call_args[0][0]
    assert "bỏ qua" in reply_text.lower() or "Bỏ qua" in reply_text


@pytest.mark.asyncio
async def test_none_message_returns_silently(conn, monkeypatch):
    """query.message is None (deleted message): spinner cleared, no crash, no DB change."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)

    update, query = make_update(f"done:{task_id}:{due}", user_id=999)
    query.message = None  # simulate deleted message

    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    query.answer.assert_called_once()
    # task must not have advanced
    row = task_repo.get_task_by_id(conn, task_id)
    assert row["next_due_date"] == due


@pytest.mark.asyncio
async def test_stale_button_no_db_change(conn, monkeypatch):
    """Stale callback: task already advanced — no DB change, popup alert."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    old_due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, old_due)
    # Simulate task already advanced to next cycle
    new_due = (date.fromisoformat(old_due) + timedelta(days=30)).isoformat()
    task_repo.advance_next_due_date(conn, task_id, new_due)

    update, query = make_update(f"done:{task_id}:{old_due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    # task still at new_due — not moved again
    row = task_repo.get_task_by_id(conn, task_id)
    assert row["next_due_date"] == new_due

    # spinner cleared exactly once (bare answer, no show_alert)
    query.answer.assert_called_once_with()
    # stale message sent via reply_text
    query.message.reply_text.assert_called_once()
    reply_text = query.message.reply_text.call_args[0][0]
    assert "hết hiệu lực" in reply_text


@pytest.mark.asyncio
async def test_stale_button_deleted_task(conn, monkeypatch):
    """Stale callback: task deleted — no crash, popup alert, no DB change."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    task_repo.delete_task(conn, task_id)

    update, query = make_update(f"done:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    # spinner cleared exactly once
    query.answer.assert_called_once_with()
    # stale message sent via reply_text
    query.message.reply_text.assert_called_once()
    reply_text = query.message.reply_text.call_args[0][0]
    assert "hết hiệu lực" in reply_text


@pytest.mark.asyncio
async def test_non_admin_callback_silently_ignored(conn, monkeypatch):
    """Non-admin user: spinner cleared, no DB changes."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    # user_id=111 is not admin
    update, query = make_update(f"done:{task_id}:{due}", user_id=111)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    # spinner cleared
    query.answer.assert_called_once()
    # no reply message
    query.message.reply_text.assert_not_called()
    # task not advanced
    row = task_repo.get_task_by_id(conn, task_id)
    assert row["next_due_date"] == due


@pytest.mark.asyncio
async def test_reply_contains_new_due_date_formatted(conn, monkeypatch):
    """Done reply contains the new due date in DD/MM/YYYY format."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = "2026-07-01"
    task_id = task_repo.create_task(conn, "T", 30, due)
    reminder_log_repo.log_sent(conn, task_id, "D-0", due + "T08:00:00Z")

    update, query = make_update(f"done:{task_id}:{due}", user_id=999)
    context = make_context(conn)

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    reply_text = query.message.reply_text.call_args[0][0]
    # new_due = 2026-07-01 + 30 days = 2026-07-31, displayed as 31/07/2026
    assert "31/07/2026" in reply_text
