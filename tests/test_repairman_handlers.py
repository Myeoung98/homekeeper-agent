"""Tests for homekeeper/bot/repairman_handlers.py (Story 3.1)."""

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from homekeeper.db.repairman_repo import create_repairman


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
    context.args = args if args is not None else []

    return update, context


@pytest.fixture(autouse=True)
def patch_admin():
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield


# ---------------------------------------------------------------------------
# AC-6: Member rejection with domain-specific message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_repairman_cmd_rejects_non_admin(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, user_id=99999, args=["list"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Bạn không có quyền quản lý danh bạ thợ." == text


@pytest.mark.asyncio
async def test_repairman_cmd_admin_gets_through(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=["list"])
    result = await repairman_cmd(update, context)
    # admin passes — does not get rejection message
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Bạn không có quyền quản lý danh bạ thợ." not in text


# ---------------------------------------------------------------------------
# AC-3 / AC-4: list subcommand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=["list"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có thợ nào trong danh bạ" in text
    assert "/repairman add" in text


@pytest.mark.asyncio
async def test_list_with_repairmen(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    create_repairman(conn, "Thợ A", "0901234567", "điều hòa")
    create_repairman(conn, "Thợ B", "0912345678", "điện lạnh")
    update, context = _make_uc(conn, args=["list"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Thợ A" in text
    assert "0901234567" in text
    assert "điều hòa" in text
    assert "Thợ B" in text


# ---------------------------------------------------------------------------
# AC-1 / AC-2: add subcommand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_start_asks_name(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd, ASK_ADD_NAME
    update, context = _make_uc(conn, args=["add"])
    result = await repairman_cmd(update, context)
    assert result == ASK_ADD_NAME
    text = update.effective_message.reply_text.call_args[0][0]
    assert "tên" in text.lower() or "Tên" in text


@pytest.mark.asyncio
async def test_add_name_empty_rejected(conn):
    from homekeeper.bot.repairman_handlers import receive_add_name, ASK_ADD_NAME
    update, context = _make_uc(conn, text="  ")
    result = await receive_add_name(update, context)
    assert result == ASK_ADD_NAME
    assert update.effective_message.reply_text.called


@pytest.mark.asyncio
async def test_add_name_stored_asks_phone(conn):
    from homekeeper.bot.repairman_handlers import receive_add_name, ASK_ADD_PHONE
    update, context = _make_uc(conn, text="Nguyễn Văn A")
    result = await receive_add_name(update, context)
    assert result == ASK_ADD_PHONE
    assert context.user_data["add_name"] == "Nguyễn Văn A"


@pytest.mark.asyncio
async def test_add_phone_empty_rejected(conn):
    from homekeeper.bot.repairman_handlers import receive_add_phone, ASK_ADD_PHONE
    update, context = _make_uc(conn, text="  ")
    context.user_data["add_name"] = "Thợ"
    result = await receive_add_phone(update, context)
    assert result == ASK_ADD_PHONE


@pytest.mark.asyncio
async def test_add_phone_stored_asks_service(conn):
    from homekeeper.bot.repairman_handlers import receive_add_phone, ASK_ADD_SERVICE
    update, context = _make_uc(conn, text="0901234567")
    context.user_data["add_name"] = "Thợ"
    result = await receive_add_phone(update, context)
    assert result == ASK_ADD_SERVICE
    assert context.user_data["add_phone"] == "0901234567"


@pytest.mark.asyncio
async def test_add_service_empty_rejected(conn):
    from homekeeper.bot.repairman_handlers import receive_add_service, ASK_ADD_SERVICE
    update, context = _make_uc(conn, text="  ")
    context.user_data["add_name"] = "Thợ"
    context.user_data["add_phone"] = "09090909"
    result = await receive_add_service(update, context)
    assert result == ASK_ADD_SERVICE


@pytest.mark.asyncio
async def test_add_service_saves_and_confirms(conn):
    from homekeeper.bot.repairman_handlers import receive_add_service
    from homekeeper.db.repairman_repo import get_all_repairmen
    update, context = _make_uc(conn, text="điều hòa, tủ lạnh")
    context.user_data["add_name"] = "Thợ Hùng"
    context.user_data["add_phone"] = "0901234567"
    result = await receive_add_service(update, context)
    assert result == ConversationHandler.END
    rows = get_all_repairmen(conn)
    assert len(rows) == 1
    assert rows[0]["name"] == "Thợ Hùng"
    assert rows[0]["phone"] == "0901234567"
    assert rows[0]["service_type"] == "điều hòa, tủ lạnh"


@pytest.mark.asyncio
async def test_add_confirm_message_format(conn):
    from homekeeper.bot.repairman_handlers import receive_add_service
    update, context = _make_uc(conn, text="điều hòa")
    context.user_data["add_name"] = "Thợ Hùng"
    context.user_data["add_phone"] = "0901234567"
    await receive_add_service(update, context)
    reply_text = update.effective_message.reply_text.call_args[0][0]
    assert "✅ Đã thêm thợ:" in reply_text
    assert "Thợ Hùng" in reply_text
    assert "0901234567" in reply_text
    assert "điều hòa" in reply_text


# ---------------------------------------------------------------------------
# AC-5: edit subcommand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_empty_db_returns_end(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=["edit"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Chưa có thợ" in text or "chưa có thợ" in text


@pytest.mark.asyncio
async def test_edit_shows_list_and_returns_edit_select(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd, EDIT_SELECT
    create_repairman(conn, "Thợ A", "09", "AC")
    update, context = _make_uc(conn, args=["edit"])
    result = await repairman_cmd(update, context)
    assert result == EDIT_SELECT
    assert "edit_repairman_ids" in context.user_data


@pytest.mark.asyncio
async def test_edit_select_invalid_number(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_select, EDIT_SELECT
    create_repairman(conn, "Thợ A", "09", "AC")
    update, context = _make_uc(conn, text="5")
    context.user_data["edit_repairman_ids"] = [1]
    result = await receive_edit_select(update, context)
    assert result == EDIT_SELECT


@pytest.mark.asyncio
async def test_edit_select_valid_asks_name(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_select, EDIT_NAME
    rid = create_repairman(conn, "Thợ A", "09", "AC")
    update, context = _make_uc(conn, text="1")
    context.user_data["edit_repairman_ids"] = [rid]
    result = await receive_edit_select(update, context)
    assert result == EDIT_NAME
    assert "edit_repairman" in context.user_data


@pytest.mark.asyncio
async def test_edit_name_keep_old(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_name, EDIT_PHONE
    update, context = _make_uc(conn, text="-")
    context.user_data["edit_repairman"] = {"id": 1, "name": "Old", "phone": "09", "service_type": "AC"}
    result = await receive_edit_name(update, context)
    assert result == EDIT_PHONE
    assert context.user_data["edit_name"] == "Old"


@pytest.mark.asyncio
async def test_edit_name_new_value(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_name, EDIT_PHONE
    update, context = _make_uc(conn, text="New Name")
    context.user_data["edit_repairman"] = {"id": 1, "name": "Old", "phone": "09", "service_type": "AC"}
    result = await receive_edit_name(update, context)
    assert result == EDIT_PHONE
    assert context.user_data["edit_name"] == "New Name"


@pytest.mark.asyncio
async def test_edit_phone_keep_old(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_phone, EDIT_SERVICE
    update, context = _make_uc(conn, text="-")
    context.user_data["edit_repairman"] = {"id": 1, "name": "N", "phone": "0900", "service_type": "AC"}
    context.user_data["edit_name"] = "N"
    result = await receive_edit_phone(update, context)
    assert result == EDIT_SERVICE
    assert context.user_data["edit_phone"] == "0900"


@pytest.mark.asyncio
async def test_edit_service_saves_and_confirms(conn):
    from homekeeper.bot.repairman_handlers import receive_edit_service
    from homekeeper.db.repairman_repo import get_repairman_by_id
    rid = create_repairman(conn, "Old Name", "0900", "old service")
    update, context = _make_uc(conn, text="new service")
    context.user_data["edit_repairman"] = {"id": rid, "name": "Old Name", "phone": "0900", "service_type": "old service"}
    context.user_data["edit_name"] = "New Name"
    context.user_data["edit_phone"] = "0911"
    result = await receive_edit_service(update, context)
    assert result == ConversationHandler.END
    row = get_repairman_by_id(conn, rid)
    assert row["name"] == "New Name"
    assert row["phone"] == "0911"
    assert row["service_type"] == "new service"
    text = update.effective_message.reply_text.call_args[0][0]
    assert "✅ Đã cập nhật thợ:" in text


# ---------------------------------------------------------------------------
# AC-5: delete subcommand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_empty_db_returns_end(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=["delete"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_delete_shows_list_and_returns_delete_select(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd, DELETE_SELECT
    create_repairman(conn, "Thợ A", "09", "AC")
    update, context = _make_uc(conn, args=["delete"])
    result = await repairman_cmd(update, context)
    assert result == DELETE_SELECT
    assert "delete_repairman_ids" in context.user_data


@pytest.mark.asyncio
async def test_delete_select_invalid_returns_delete_select(conn):
    from homekeeper.bot.repairman_handlers import receive_delete_select, DELETE_SELECT
    update, context = _make_uc(conn, text="99")
    context.user_data["delete_repairman_ids"] = [1]
    result = await receive_delete_select(update, context)
    assert result == DELETE_SELECT


@pytest.mark.asyncio
async def test_delete_select_valid_asks_confirm(conn):
    from homekeeper.bot.repairman_handlers import receive_delete_select, DELETE_CONFIRM
    rid = create_repairman(conn, "Thợ A", "09", "AC")
    update, context = _make_uc(conn, text="1")
    context.user_data["delete_repairman_ids"] = [rid]
    result = await receive_delete_select(update, context)
    assert result == DELETE_CONFIRM
    assert "delete_repairman" in context.user_data
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Có" in text and "Không" in text


@pytest.mark.asyncio
async def test_delete_confirm_co_deletes(conn):
    from homekeeper.bot.repairman_handlers import receive_delete_confirm
    from homekeeper.db.repairman_repo import get_repairman_by_id
    rid = create_repairman(conn, "Thợ X", "09", "AC")
    update, context = _make_uc(conn, text="Có")
    context.user_data["delete_repairman"] = {"id": rid, "name": "Thợ X"}
    result = await receive_delete_confirm(update, context)
    assert result == ConversationHandler.END
    assert get_repairman_by_id(conn, rid) is None
    text = update.effective_message.reply_text.call_args[0][0]
    assert "✅ Đã xóa thợ:" in text
    assert "Thợ X" in text


@pytest.mark.asyncio
async def test_delete_confirm_khong_cancels(conn):
    from homekeeper.bot.repairman_handlers import receive_delete_confirm
    from homekeeper.db.repairman_repo import get_repairman_by_id
    rid = create_repairman(conn, "Thợ X", "09", "AC")
    update, context = _make_uc(conn, text="Không")
    context.user_data["delete_repairman"] = {"id": rid, "name": "Thợ X"}
    result = await receive_delete_confirm(update, context)
    assert result == ConversationHandler.END
    assert get_repairman_by_id(conn, rid) is not None
    text = update.effective_message.reply_text.call_args[0][0]
    assert "Đã hủy" in text


@pytest.mark.asyncio
async def test_delete_confirm_case_insensitive(conn):
    from homekeeper.bot.repairman_handlers import receive_delete_confirm
    from homekeeper.db.repairman_repo import get_repairman_by_id
    rid = create_repairman(conn, "Thợ X", "09", "AC")
    update, context = _make_uc(conn, text="có")
    context.user_data["delete_repairman"] = {"id": rid, "name": "Thợ X"}
    result = await receive_delete_confirm(update, context)
    assert get_repairman_by_id(conn, rid) is None


# ---------------------------------------------------------------------------
# Unknown subcommand
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_subcommand_shows_usage(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=["unknown"])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
    text = update.effective_message.reply_text.call_args[0][0]
    assert "/repairman" in text


@pytest.mark.asyncio
async def test_no_args_shows_usage(conn):
    from homekeeper.bot.repairman_handlers import repairman_cmd
    update, context = _make_uc(conn, args=[])
    result = await repairman_cmd(update, context)
    assert result == ConversationHandler.END
