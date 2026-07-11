import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from homekeeper.bot.member_handlers import (
    ASK_ADD_ID,
    ASK_ADD_NAME,
    REMOVE_CONFIRM,
    REMOVE_SELECT,
    build_member_conversation,
    member_cmd,
    member_cancel,
    receive_add_id,
    receive_add_name,
    receive_remove_confirm,
    receive_remove_select,
)
from homekeeper.db import member_repo as _member_repo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


@pytest.fixture(autouse=True)
def patch_admin():
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield


def _make_uc(conn, text="", user_id=12345, args=None):
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.text = text
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = message
    application = MagicMock()
    application.bot_data = {"db": conn}
    context = MagicMock()
    context.application = application
    context.user_data = {}
    context.args = args or []
    return update, context


def _seed_member(conn, telegram_user_id=99001, name="Test Member"):
    _member_repo.add_member(conn, telegram_user_id, name)
    return _member_repo.get_member_by_telegram_id(conn, telegram_user_id)


# ---------------------------------------------------------------------------
# Auth tests (AC-6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_user_rejected(conn):
    update, context = _make_uc(conn, user_id=99999, args=["add"])
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END
    update.effective_message.reply_text.assert_called_once_with(
        "Bạn không có quyền quản lý thành viên."
    )


@pytest.mark.asyncio
async def test_admin_can_access_add(conn):
    update, context = _make_uc(conn, user_id=12345, args=["add"])
    result = await member_cmd(update, context)
    assert result == ASK_ADD_ID


@pytest.mark.asyncio
async def test_effective_user_none_returns_end(conn):
    update, context = _make_uc(conn, args=["add"])
    update.effective_user = None
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_unknown_subcommand_shows_usage(conn):
    update, context = _make_uc(conn, args=["unknown"])
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END
    update.effective_message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# Add flow — receive_add_id (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_invalid_id_rejected(conn):
    update, context = _make_uc(conn, text="abc")
    result = await receive_add_id(update, context)
    assert result == ASK_ADD_ID


@pytest.mark.asyncio
async def test_add_zero_id_rejected(conn):
    update, context = _make_uc(conn, text="0")
    result = await receive_add_id(update, context)
    assert result == ASK_ADD_ID


@pytest.mark.asyncio
async def test_add_negative_id_rejected(conn):
    update, context = _make_uc(conn, text="-1")
    result = await receive_add_id(update, context)
    assert result == ASK_ADD_ID


@pytest.mark.asyncio
async def test_add_valid_id_asks_name(conn):
    update, context = _make_uc(conn, text="123456789")
    result = await receive_add_id(update, context)
    assert result == ASK_ADD_NAME
    assert context.user_data["add_telegram_id"] == 123456789


@pytest.mark.asyncio
async def test_add_duplicate_id_shows_message(conn):
    _seed_member(conn, telegram_user_id=123456789, name="Existing")
    update, context = _make_uc(conn, text="123456789")
    result = await receive_add_id(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "đã có" in text


# ---------------------------------------------------------------------------
# Add flow — receive_add_name (AC-2)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_empty_name_rejected(conn):
    update, context = _make_uc(conn, text="   ")
    context.user_data["add_telegram_id"] = 123456789
    result = await receive_add_name(update, context)
    assert result == ASK_ADD_NAME


@pytest.mark.asyncio
async def test_add_valid_name_saves_member(conn):
    update, context = _make_uc(conn, text="Nguyen Van A")
    context.user_data["add_telegram_id"] = 123456789
    result = await receive_add_name(update, context)
    assert result == ConversationHandler.END
    row = _member_repo.get_member_by_telegram_id(conn, 123456789)
    assert row is not None
    assert row["name"] == "Nguyen Van A"


@pytest.mark.asyncio
async def test_add_confirmation_contains_name_and_id(conn):
    update, context = _make_uc(conn, text="Nguyen Van A")
    context.user_data["add_telegram_id"] = 123456789
    await receive_add_name(update, context)
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Nguyen Van A" in text
    assert "123456789" in text


@pytest.mark.asyncio
async def test_add_confirmation_uses_html(conn):
    update, context = _make_uc(conn, text="Name")
    context.user_data["add_telegram_id"] = 123456789
    await receive_add_name(update, context)
    call_kwargs = update.effective_message.reply_text.call_args
    assert call_kwargs.kwargs.get("parse_mode") == "HTML"


# ---------------------------------------------------------------------------
# List (AC-4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_empty_db(conn):
    update, context = _make_uc(conn, args=["list"])
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có thành viên nào" in text


@pytest.mark.asyncio
async def test_list_shows_all_members(conn):
    _seed_member(conn, telegram_user_id=10001, name="Alice")
    _seed_member(conn, telegram_user_id=10002, name="Bob")
    update, context = _make_uc(conn, args=["list"])
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Alice" in text
    assert "Bob" in text


@pytest.mark.asyncio
async def test_list_shows_telegram_user_id(conn):
    _seed_member(conn, telegram_user_id=10001, name="Alice")
    update, context = _make_uc(conn, args=["list"])
    await member_cmd(update, context)
    text = update.effective_message.reply_text.call_args[0][0]
    assert "10001" in text


# ---------------------------------------------------------------------------
# Remove flow (AC-5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_empty_db(conn):
    update, context = _make_uc(conn, args=["remove"])
    result = await member_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có thành viên nào" in text


@pytest.mark.asyncio
async def test_remove_select_shows_numbered_list(conn):
    _seed_member(conn, telegram_user_id=20001, name="Charlie")
    update, context = _make_uc(conn, args=["remove"])
    result = await member_cmd(update, context)
    assert result == REMOVE_SELECT
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Charlie" in text


@pytest.mark.asyncio
async def test_remove_select_invalid_number_rejected(conn):
    _seed_member(conn, telegram_user_id=20001, name="Charlie")
    update, context = _make_uc(conn, args=["remove"])
    await member_cmd(update, context)
    member_ids = context.user_data.get("remove_member_ids", [])
    # Now simulate selecting out-of-range number
    update2, context2 = _make_uc(conn, text="99")
    context2.user_data["remove_member_ids"] = member_ids
    result = await receive_remove_select(update2, context2)
    assert result == REMOVE_SELECT


@pytest.mark.asyncio
async def test_remove_confirm_co_deletes_member(conn):
    row = _seed_member(conn, telegram_user_id=30001, name="Dave")
    update, context = _make_uc(conn, text="Có")
    context.user_data["remove_member"] = {"id": row["id"], "name": "Dave", "telegram_user_id": 30001}
    result = await receive_remove_confirm(update, context)
    assert result == ConversationHandler.END
    after = _member_repo.get_member_by_telegram_id(conn, 30001)
    assert after is None


@pytest.mark.asyncio
async def test_remove_confirm_khong_cancels(conn):
    row = _seed_member(conn, telegram_user_id=30002, name="Eve")
    update, context = _make_uc(conn, text="Không")
    context.user_data["remove_member"] = {"id": row["id"], "name": "Eve", "telegram_user_id": 30002}
    result = await receive_remove_confirm(update, context)
    assert result == ConversationHandler.END
    after = _member_repo.get_member_by_telegram_id(conn, 30002)
    assert after is not None


@pytest.mark.asyncio
async def test_remove_select_deleted_member_returns_end(conn):
    """TOCTOU: member_id in snapshot but deleted from DB before selection is processed."""
    row = _seed_member(conn, telegram_user_id=20099, name="Ghost")
    member_id = row["id"]
    _member_repo.delete_member(conn, member_id)
    update, context = _make_uc(conn, text="1")
    context.user_data["remove_member_ids"] = [member_id]
    result = await receive_remove_select(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "không còn tồn tại" in text


@pytest.mark.asyncio
async def test_remove_confirm_co_shows_confirmation(conn):
    row = _seed_member(conn, telegram_user_id=30003, name="Frank")
    update, context = _make_uc(conn, text="Có")
    context.user_data["remove_member"] = {"id": row["id"], "name": "Frank", "telegram_user_id": 30003}
    await receive_remove_confirm(update, context)
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Frank" in text
    assert "✅" in text


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def test_build_member_conversation_returns_handler(conn):
    handler = build_member_conversation()
    assert isinstance(handler, ConversationHandler)
