"""Tests for edit conversation handlers in task_handlers (Story 1.4)."""

import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homekeeper.bot.task_handlers import (
    edit_start,
    receive_edit_select,
    receive_edit_name,
    receive_edit_cycle,
    receive_edit_date,
    edit_cancel,
    EDIT_SELECT,
    EDIT_NAME,
    EDIT_CYCLE,
    EDIT_DATE,
)
from homekeeper.db.task_repo import create_task
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


# ── edit_start ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_start_empty_db_returns_end(conn):
    update, context = _make_update_context(conn)
    result = await edit_start(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có công việc nào để sửa" in msg


@pytest.mark.asyncio
async def test_edit_start_lists_tasks_and_returns_edit_select(conn):
    create_task(conn, "Thay lõi lọc", 90, "2099-09-01")
    update, context = _make_update_context(conn)
    result = await edit_start(update, context)
    assert result == EDIT_SELECT
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Thay lõi lọc" in msg
    assert "1." in msg
    assert "edit_task_ids" in context.user_data


@pytest.mark.asyncio
async def test_edit_start_html_escapes_task_name(conn):
    create_task(conn, "Task <b>bold</b>", 30, "2099-07-01")
    update, context = _make_update_context(conn)
    await edit_start(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<b>bold</b>" not in msg
    assert "&lt;b&gt;" in msg


@pytest.mark.asyncio
async def test_edit_start_db_error_returns_end(conn):
    update, context = _make_update_context(conn)
    context.application.bot_data = {"db": None}
    result = await edit_start(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Không thể tải" in msg


# ── receive_edit_select ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_select_valid_stores_task_and_prompts_name(conn):
    task_id = create_task(conn, "Vệ sinh máy lọc", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="1")
    context.user_data["edit_task_ids"] = [task_id]
    result = await receive_edit_select(update, context)
    assert result == EDIT_NAME
    assert context.user_data["edit_task"]["name"] == "Vệ sinh máy lọc"
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Vệ sinh máy lọc" in msg


@pytest.mark.asyncio
async def test_receive_edit_select_invalid_number_re_prompts(conn):
    task_id = create_task(conn, "Task A", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="5")
    context.user_data["edit_task_ids"] = [task_id]
    result = await receive_edit_select(update, context)
    assert result == EDIT_SELECT


@pytest.mark.asyncio
async def test_receive_edit_select_non_digit_re_prompts(conn):
    task_id = create_task(conn, "Task A", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="abc")
    context.user_data["edit_task_ids"] = [task_id]
    result = await receive_edit_select(update, context)
    assert result == EDIT_SELECT


@pytest.mark.asyncio
async def test_receive_edit_select_stores_as_dict(conn):
    """Row must be converted to dict for safe cross-handler access."""
    task_id = create_task(conn, "Task X", 45, "2099-08-01")
    update, context = _make_update_context(conn, text="1")
    context.user_data["edit_task_ids"] = [task_id]
    await receive_edit_select(update, context)
    assert isinstance(context.user_data["edit_task"], dict)


# ── receive_edit_name ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_name_blank_keeps_old(conn):
    task_id = create_task(conn, "Old Name", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="")
    context.user_data["edit_task"] = {"id": task_id, "name": "Old Name", "cycle_days": 30, "next_due_date": "2099-07-01"}
    result = await receive_edit_name(update, context)
    assert result == EDIT_CYCLE
    assert context.user_data["edit_name"] == "Old Name"


@pytest.mark.asyncio
async def test_receive_edit_name_dash_keeps_old(conn):
    task_id = create_task(conn, "Old Name", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="-")
    context.user_data["edit_task"] = {"id": task_id, "name": "Old Name", "cycle_days": 30, "next_due_date": "2099-07-01"}
    result = await receive_edit_name(update, context)
    assert context.user_data["edit_name"] == "Old Name"


@pytest.mark.asyncio
async def test_receive_edit_name_new_name_stored(conn):
    task_id = create_task(conn, "Old", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="New Name")
    context.user_data["edit_task"] = {"id": task_id, "name": "Old", "cycle_days": 30, "next_due_date": "2099-07-01"}
    result = await receive_edit_name(update, context)
    assert result == EDIT_CYCLE
    assert context.user_data["edit_name"] == "New Name"


@pytest.mark.asyncio
async def test_receive_edit_name_too_long_re_prompts(conn):
    task_id = create_task(conn, "Old", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="x" * 201)
    context.user_data["edit_task"] = {"id": task_id, "name": "Old", "cycle_days": 30, "next_due_date": "2099-07-01"}
    result = await receive_edit_name(update, context)
    assert result == EDIT_NAME


# ── receive_edit_cycle ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_cycle_blank_keeps_old(conn):
    update, context = _make_update_context(conn, text="")
    context.user_data["edit_task"] = {"id": 1, "name": "X", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "X"
    result = await receive_edit_cycle(update, context)
    assert result == EDIT_DATE
    assert context.user_data["edit_cycle"] == 30


@pytest.mark.asyncio
async def test_receive_edit_cycle_new_value_stored(conn):
    update, context = _make_update_context(conn, text="90")
    context.user_data["edit_task"] = {"id": 1, "name": "X", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "X"
    result = await receive_edit_cycle(update, context)
    assert result == EDIT_DATE
    assert context.user_data["edit_cycle"] == 90


@pytest.mark.asyncio
async def test_receive_edit_cycle_invalid_re_prompts(conn):
    update, context = _make_update_context(conn, text="abc")
    context.user_data["edit_task"] = {"id": 1, "name": "X", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "X"
    result = await receive_edit_cycle(update, context)
    assert result == EDIT_CYCLE


# ── receive_edit_date ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_date_saves_and_confirms(conn):
    task_id = create_task(conn, "Task", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="15/08/2099")
    context.user_data["edit_task"] = {"id": task_id, "name": "Task", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "Task"
    context.user_data["edit_cycle"] = 30
    result = await receive_edit_date(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "✅ Đã cập nhật" in msg
    assert "15/08/2099" in msg


@pytest.mark.asyncio
async def test_receive_edit_date_blank_keeps_old_date(conn):
    task_id = create_task(conn, "Task", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="")
    context.user_data["edit_task"] = {"id": task_id, "name": "Task", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "Task"
    context.user_data["edit_cycle"] = 30
    result = await receive_edit_date(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "01/07/2099" in msg


@pytest.mark.asyncio
async def test_receive_edit_date_invalid_format_re_prompts(conn):
    update, context = _make_update_context(conn, text="2099-08-15")
    context.user_data["edit_task"] = {"id": 1, "name": "Task", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "Task"
    context.user_data["edit_cycle"] = 30
    result = await receive_edit_date(update, context)
    assert result == EDIT_DATE


@pytest.mark.asyncio
async def test_receive_edit_date_db_error_returns_end(conn):
    update, context = _make_update_context(conn, text="15/08/2099")
    context.user_data["edit_task"] = {"id": 1, "name": "Task", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "Task"
    context.user_data["edit_cycle"] = 30
    context.application.bot_data = {"db": None}  # break DB
    result = await receive_edit_date(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "Không thể cập nhật" in msg


@pytest.mark.asyncio
async def test_receive_edit_date_html_escapes_name(conn):
    task_id = create_task(conn, "Task <script>", 30, "2099-07-01")
    update, context = _make_update_context(conn, text="15/08/2099")
    context.user_data["edit_task"] = {"id": task_id, "name": "Task <script>", "cycle_days": 30, "next_due_date": "2099-07-01"}
    context.user_data["edit_name"] = "Task <script>"
    context.user_data["edit_cycle"] = 30
    result = await receive_edit_date(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg


# ── edit_cancel ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edit_cancel_returns_end(conn):
    update, context = _make_update_context(conn)
    result = await edit_cancel(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "hủy" in msg.lower()


# ── Patch P1: receive_edit_cycle None-guard ──────────────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_cycle_task_none_returns_end(conn):
    """P1: receive_edit_cycle must guard against task being None."""
    update, context = _make_update_context(conn, text="30")
    # edit_task not set in user_data → task is None
    result = await receive_edit_cycle(update, context)
    assert result == ConversationHandler.END
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "lỗi" in msg.lower() or "bắt đầu lại" in msg.lower()


# ── Patch P2: receive_edit_date keep-old branch fromisoformat guard ──────────

@pytest.mark.asyncio
async def test_receive_edit_date_keep_old_malformed_stored_date_re_prompts(conn):
    """P2: keep-old branch must handle malformed stored next_due_date gracefully."""
    update, context = _make_update_context(conn, text="-")
    context.user_data["edit_task"] = {
        "id": 1, "name": "Task", "cycle_days": 30,
        "next_due_date": "2099-07-01T00:00:00",  # malformed (datetime string)
    }
    context.user_data["edit_name"] = "Task"
    context.user_data["edit_cycle"] = 30
    result = await receive_edit_date(update, context)
    assert result == EDIT_DATE
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "không hợp lệ" in msg.lower() or "nhập" in msg.lower()


# ── Patch P3: receive_edit_cycle date display format ────────────────────────

@pytest.mark.asyncio
async def test_receive_edit_cycle_displays_date_in_ddmmyyyy(conn):
    """P3: receive_edit_cycle prompt must display next_due_date as DD/MM/YYYY."""
    update, context = _make_update_context(conn, text="60")
    context.user_data["edit_task"] = {
        "id": 1, "name": "Task", "cycle_days": 30,
        "next_due_date": "2099-07-15",
    }
    context.user_data["edit_name"] = "Task"
    result = await receive_edit_cycle(update, context)
    assert result == EDIT_DATE
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "15/07/2099" in msg
    assert "2099-07-15" not in msg
