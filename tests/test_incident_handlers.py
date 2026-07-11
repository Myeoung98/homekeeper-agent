import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homekeeper.db import incident_repo as _incident_repo

import pytest
from telegram.ext import ConversationHandler

from homekeeper.bot.incident_handlers import (
    ASK_DESC,
    INCIDENT_NO_PATTERN,
    INCIDENT_YES_PATTERN,
    build_incident_conversation,
    incident_cmd,
    incident_no_callback,
    incident_yes_callback,
    receive_description,
)


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


def _make_callback_uc(conn, callback_data="incident_no", user_id=12345):
    query = MagicMock()
    query.data = callback_data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.edit_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    application = MagicMock()
    application.bot_data = {"db": conn}
    context = MagicMock()
    context.application = application
    context.bot_data = {"db": conn}
    return update, context


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

def test_incident_no_pattern():
    import re
    assert re.match(INCIDENT_NO_PATTERN, "incident_no")
    assert not re.match(INCIDENT_NO_PATTERN, "incident_yes:1")


def test_incident_yes_pattern():
    import re
    assert re.match(INCIDENT_YES_PATTERN, "incident_yes:1")
    assert re.match(INCIDENT_YES_PATTERN, "incident_yes:999")
    assert not re.match(INCIDENT_YES_PATTERN, "incident_no")


# ---------------------------------------------------------------------------
# Task 2: incident_cmd — auth + prompt (AC-1, AC-5)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_user_rejected(conn):
    update, context = _make_uc(conn, user_id=99999)
    result = await incident_cmd(update, context)
    assert result == ConversationHandler.END
    update.effective_message.reply_text.assert_called_once_with(
        "Bạn không có quyền sử dụng bot này."
    )


@pytest.mark.asyncio
async def test_admin_can_access(conn):
    update, context = _make_uc(conn, user_id=12345)
    result = await incident_cmd(update, context)
    assert result == ASK_DESC
    update.effective_message.reply_text.assert_called_once()
    call_args = update.effective_message.reply_text.call_args[0][0]
    assert "Mô tả sự cố" in call_args


@pytest.mark.asyncio
async def test_registered_member_can_access(conn):
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (99999, 'Test Member')")
    conn.commit()
    update, context = _make_uc(conn, user_id=99999)
    result = await incident_cmd(update, context)
    assert result == ASK_DESC


@pytest.mark.asyncio
async def test_incident_cmd_shows_description_prompt(conn):
    update, context = _make_uc(conn, user_id=12345)
    await incident_cmd(update, context)
    prompt = update.effective_message.reply_text.call_args[0][0]
    assert "điều hòa phòng ngủ không mát" in prompt


# ---------------------------------------------------------------------------
# Task 3: receive_description — save + keyboard (AC-2, AC-4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_description_rejected(conn):
    update, context = _make_uc(conn, text="   ", user_id=12345)
    result = await receive_description(update, context)
    assert result == ASK_DESC
    row = conn.execute("SELECT COUNT(*) FROM INCIDENT").fetchone()[0]
    assert row == 0
    update.effective_message.reply_text.assert_called_once()
    prompt = update.effective_message.reply_text.call_args[0][0]
    assert "trống" in prompt or "Nhập lại" in prompt


@pytest.mark.asyncio
async def test_empty_string_description_rejected(conn):
    update, context = _make_uc(conn, text="", user_id=12345)
    result = await receive_description(update, context)
    assert result == ASK_DESC


@pytest.mark.asyncio
async def test_valid_description_saves_incident(conn):
    update, context = _make_uc(conn, text="Điều hòa hỏng", user_id=12345)
    result = await receive_description(update, context)
    assert result == ConversationHandler.END
    row = conn.execute("SELECT * FROM INCIDENT WHERE id=1").fetchone()
    assert row is not None
    assert row["reported_by"] == 12345
    assert row["description"] == "Điều hòa hỏng"


@pytest.mark.asyncio
async def test_valid_description_sends_keyboard(conn):
    update, context = _make_uc(conn, text="Ống nước vỡ", user_id=12345)
    await receive_description(update, context)
    update.effective_message.reply_text.assert_called_once()
    call_kwargs = update.effective_message.reply_text.call_args
    # Must include reply_markup keyword argument
    assert call_kwargs.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_keyboard_has_co_and_khong_buttons(conn):
    update, context = _make_uc(conn, text="Quạt hỏng", user_id=12345)
    await receive_description(update, context)
    keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    buttons = [btn for row in keyboard.inline_keyboard for btn in row]
    labels = [b.text for b in buttons]
    assert "Có" in labels
    assert "Không" in labels


@pytest.mark.asyncio
async def test_co_button_callback_data_includes_incident_id(conn):
    update, context = _make_uc(conn, text="Bóng đèn cháy", user_id=12345)
    await receive_description(update, context)
    keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    buttons = {b.text: b.callback_data for row in keyboard.inline_keyboard for b in row}
    assert buttons["Có"].startswith("incident_yes:")
    incident_id = int(buttons["Có"].split(":")[1])
    assert incident_id >= 1


@pytest.mark.asyncio
async def test_khong_button_callback_data(conn):
    update, context = _make_uc(conn, text="Cửa kẹt", user_id=12345)
    await receive_description(update, context)
    keyboard = update.effective_message.reply_text.call_args.kwargs["reply_markup"]
    buttons = {b.text: b.callback_data for row in keyboard.inline_keyboard for b in row}
    assert buttons["Không"] == "incident_no"


@pytest.mark.asyncio
async def test_ask_repairman_message_text(conn):
    update, context = _make_uc(conn, text="Rò điện", user_id=12345)
    await receive_description(update, context)
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "tìm thợ sửa" in msg


# ---------------------------------------------------------------------------
# Task 4: incident_no_callback (AC-3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_incident_no_callback_answers_query(conn):
    update, context = _make_callback_uc(conn, callback_data="incident_no")
    await incident_no_callback(update, context)
    update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_incident_no_callback_sends_confirmation(conn):
    update, context = _make_callback_uc(conn, callback_data="incident_no")
    await incident_no_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once_with(
        "✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ."
    )


# ---------------------------------------------------------------------------
# Task 4: build_incident_conversation builder
# ---------------------------------------------------------------------------

def test_build_incident_conversation_returns_handler(conn):
    from telegram.ext import ConversationHandler
    handler = build_incident_conversation()
    assert isinstance(handler, ConversationHandler)


# ---------------------------------------------------------------------------
# Patch fixes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_member_can_access_when_admin_id_is_non_integer(conn):
    """P1: ValueError in _is_authenticated must not abort member check."""
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (99999, 'Test')")
    conn.commit()
    update, context = _make_uc(conn, user_id=99999)
    with patch.dict("os.environ", {"ADMIN_USER_ID": "not-a-number"}):
        result = await incident_cmd(update, context)
    assert result == ASK_DESC


@pytest.mark.asyncio
async def test_receive_description_db_error_keeps_conversation_open(conn):
    """P2: DB failure should return ASK_DESC so user can retry."""
    from unittest.mock import patch as mock_patch
    update, context = _make_uc(conn, text="Quạt hỏng", user_id=12345)
    with mock_patch(
        "homekeeper.bot.incident_handlers.incident_repo.create_incident",
        side_effect=Exception("DB error"),
    ):
        result = await receive_description(update, context)
    assert result == ASK_DESC
    update.effective_message.reply_text.assert_called_once()
    msg = update.effective_message.reply_text.call_args[0][0]
    assert "thử lại" in msg


@pytest.mark.asyncio
async def test_receive_description_effective_user_none(conn):
    """P4: receive_description must guard against effective_user being None."""
    update, context = _make_uc(conn, text="Valid description", user_id=12345)
    update.effective_user = None
    result = await receive_description(update, context)
    assert result == ConversationHandler.END


# ---------------------------------------------------------------------------
# Task 3: incident_yes_callback (AC-1, AC-2, AC-3, AC-4)
# ---------------------------------------------------------------------------

def _seed_incident(conn, description="điều hòa hỏng", user_id=12345):
    return _incident_repo.create_incident(conn, user_id, description)


def _seed_repairman(conn, name="Anh A", phone="0901", service_type="điều hòa"):
    conn.execute(
        "INSERT INTO REPAIRMAN (name, phone, service_type) VALUES (?, ?, ?)",
        (name, phone, service_type),
    )
    conn.commit()


@pytest.mark.asyncio
async def test_incident_yes_callback_answers_query(conn):
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_incident_yes_shows_matching_repairman(conn):
    incident_id = _seed_incident(conn, description="điều hòa hỏng")
    _seed_repairman(conn, name="Anh A", phone="0901", service_type="điều hòa")
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once()
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "Anh A" in text
    assert "0901" in text
    assert "điều hòa" in text


@pytest.mark.asyncio
async def test_incident_yes_result_contains_footnote(conn):
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "Liên hệ trực tiếp" in text


@pytest.mark.asyncio
async def test_incident_yes_no_reply_markup_in_result(conn):
    """AC-2: result must have no inline buttons."""
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    call_kwargs = update.callback_query.message.edit_text.call_args
    reply_markup = call_kwargs.kwargs.get("reply_markup")
    assert reply_markup is None


@pytest.mark.asyncio
async def test_incident_yes_empty_db_ac4(conn):
    """AC-4: empty repairman DB → specific message."""
    incident_id = _seed_incident(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "Danh bạ thợ đang trống" in text


@pytest.mark.asyncio
async def test_incident_yes_no_match_ac3(conn):
    """AC-3: no matching repairmen → specific message."""
    incident_id = _seed_incident(conn, description="điều hòa hỏng")
    _seed_repairman(conn, service_type="ống nước")
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "Không tìm thấy thợ phù hợp" in text


@pytest.mark.asyncio
async def test_incident_yes_uses_edit_text_not_reply_text(conn):
    """Must use edit_text (replaces keyboard), not reply_text."""
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once()
    update.callback_query.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_incident_yes_repairman_load_error_replies_gracefully(conn):
    """DB failure loading repairmen → graceful error, no crash."""
    from unittest.mock import patch as mock_patch
    incident_id = _seed_incident(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    with mock_patch(
        "homekeeper.bot.incident_handlers.repairman_repo.get_all_repairmen",
        side_effect=Exception("DB error"),
    ):
        await incident_yes_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once()


@pytest.mark.asyncio
async def test_incident_yes_unauthenticated_rejected(conn):
    """P1: unauthenticated user must be rejected."""
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}", user_id=99999)
    await incident_yes_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once()
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "quyền" in text


@pytest.mark.asyncio
async def test_incident_yes_query_message_none_no_crash(conn):
    """P4: query.message is None (inline context) — must not raise AttributeError."""
    incident_id = _seed_incident(conn)
    _seed_repairman(conn)
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    update.callback_query.message = None
    await incident_yes_callback(update, context)
