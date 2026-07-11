"""Tests for delete conversation handlers in task_handlers (Story 1.4)."""

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homekeeper.bot.task_handlers import (
    delete_start,
    receive_delete_select,
    receive_delete_confirm,
    delete_cancel,
    DELETE_SELECT,
    DELETE_CONFIRM,
)
from homekeeper.db.task_repo import create_task, get_task_by_id
from telegram.ext import ConversationHandler


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def _make_update_context(conn, text=""):
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.text = text

    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_message = message

    application = MagicMock()
    application.bot_data = {"db": conn}

    context = MagicMock()
    context.application = application
    context.user_data = {}

    return update, context


@pytest.fixture(autouse=True)
def patch_admin():
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield


# ── delete_start ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_start_empty_db_returns_end(conn):
    update, context = _make_update_context(conn)
    result = await delete_start(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có công việc nào để xóa" in msg


@pytest.mark.asyncio
async def test_delete_start_lists_tasks_and_returns_delete_select(conn):
    create_task(conn, "Vệ sinh điều hòa", 180, "2099-12-01")
    update, context = _make_update_context(conn)
    result = await delete_start(update, context)
    assert result == DELETE_SELECT
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Vệ sinh điều hòa" in msg
    assert "1." in msg
    assert "delete_task_ids" in context.user_data


@pytest.mark.asyncio
async def test_delete_start_html_escapes_task_name(conn):
    create_task(conn, "Task <b>bold</b>", 30, "2099-07-01")
    update, context = _make_update_context(conn)
    await delete_start(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<b>bold</b>" not in msg
    assert "&lt;b&gt;" in msg


@pytest.mark.asyncio
async def test_delete_start_db_error_returns_end(conn):
    update, context = _make_update_context(conn)
    context.application.bot_data = {"db": None}
    result = await delete_start(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Không thể tải" in msg


# ── receive_delete_select ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_delete_select_valid_prompts_confirm(conn):
    task_id = create_task(conn, "Thay bóng đèn", 365, "2099-12-01")
    update, context = _make_update_context(conn, text="1")
    context.user_data["delete_task_ids"] = [task_id]
    result = await receive_delete_select(update, context)
    assert result == DELETE_CONFIRM
    assert context.user_data["delete_task"]["name"] == "Thay bóng đèn"
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Thay bóng đèn" in msg
    assert "Có" in msg


@pytest.mark.asyncio
async def test_receive_delete_select_invalid_re_prompts(conn):
    task_id = create_task(conn, "Task A", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="99")
    context.user_data["delete_task_ids"] = [task_id]
    result = await receive_delete_select(update, context)
    assert result == DELETE_SELECT


@pytest.mark.asyncio
async def test_receive_delete_select_non_digit_re_prompts(conn):
    task_id = create_task(conn, "Task A", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="abc")
    context.user_data["delete_task_ids"] = [task_id]
    result = await receive_delete_select(update, context)
    assert result == DELETE_SELECT


@pytest.mark.asyncio
async def test_receive_delete_select_stores_as_dict(conn):
    task_id = create_task(conn, "Task X", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="1")
    context.user_data["delete_task_ids"] = [task_id]
    await receive_delete_select(update, context)
    assert isinstance(context.user_data["delete_task"], dict)


@pytest.mark.asyncio
async def test_receive_delete_select_html_escapes_name_in_confirm(conn):
    task_id = create_task(conn, "Task <script>", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="1")
    context.user_data["delete_task_ids"] = [task_id]
    await receive_delete_select(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg


# ── receive_delete_confirm ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_delete_confirm_yes_deletes_task(conn):
    task_id = create_task(conn, "Task to Delete", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="Có")
    context.user_data["delete_task"] = {"id": task_id, "name": "Task to Delete"}
    result = await receive_delete_confirm(update, context)
    assert result == ConversationHandler.END
    assert get_task_by_id(conn, task_id) is None
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "✅ Đã xóa" in msg
    assert "Task to Delete" in msg


@pytest.mark.asyncio
async def test_receive_delete_confirm_no_does_not_delete(conn):
    task_id = create_task(conn, "Task Safe", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="Không")
    context.user_data["delete_task"] = {"id": task_id, "name": "Task Safe"}
    result = await receive_delete_confirm(update, context)
    assert result == ConversationHandler.END
    assert get_task_by_id(conn, task_id) is not None
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Đã hủy xóa" in msg


@pytest.mark.asyncio
async def test_receive_delete_confirm_other_text_cancels(conn):
    task_id = create_task(conn, "Task Safe", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="blah")
    context.user_data["delete_task"] = {"id": task_id, "name": "Task Safe"}
    result = await receive_delete_confirm(update, context)
    assert result == ConversationHandler.END
    assert get_task_by_id(conn, task_id) is not None


@pytest.mark.asyncio
async def test_receive_delete_confirm_html_escapes_name(conn):
    task_id = create_task(conn, "Task <b>evil</b>", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="Có")
    context.user_data["delete_task"] = {"id": task_id, "name": "Task <b>evil</b>"}
    await receive_delete_confirm(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<b>evil</b>" not in msg
    assert "&lt;b&gt;" in msg


# ── delete_cancel ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_cancel_returns_end(conn):
    update, context = _make_update_context(conn)
    result = await delete_cancel(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "hủy" in msg.lower()
