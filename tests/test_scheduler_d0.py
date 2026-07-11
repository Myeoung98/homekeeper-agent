"""Tests for D-0 reminder logic in Story 2.3."""

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import call, patch

import pytest

from homekeeper.db import task_repo
from homekeeper.scheduler.loop import _check_d0, _tick

# The fixed VN date used by make_vn_time (matches datetime(2026, 6, 29, ...))
_VN_FIXED_DATE = "2026-06-29"


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


def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def make_vn_time(hour: int, minute: int = 0) -> datetime:
    """Return a fixed VN datetime (2026-06-29) at the given hour:minute."""
    vn_tz = timezone(timedelta(hours=7))
    return datetime(2026, 6, 29, hour, minute, 0, tzinfo=vn_tz)


# ---------------------------------------------------------------------------
# _tick integration tests for D-0
# ---------------------------------------------------------------------------


def test_tick_before_8am_skips_d0(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, _VN_FIXED_DATE)  # due on VN "today" (2026-06-29)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(7, 59))

    mock_send.assert_not_called()


def test_tick_sends_d0_for_task_due_today(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, _VN_FIXED_DATE)  # due on VN "today" (2026-06-29)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(8, 1))

    assert mock_send.call_count >= 1


def test_tick_does_not_send_d0_for_task_due_tomorrow(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    # tomorrow relative to VN fixed date 2026-06-29 is 2026-06-30
    task_repo.create_task(conn, "T", 30, "2026-06-30")

    with patch("homekeeper.scheduler.loop._check_d1"), \
         patch("homekeeper.scheduler.loop._check_d0") as mock_check_d0:
        _tick(conn, _now=make_vn_time(8, 1))

    mock_check_d0.assert_not_called()


# ---------------------------------------------------------------------------
# _check_d0 unit tests
# ---------------------------------------------------------------------------


def test_check_d0_sends_when_not_yet_sent(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean AC", 30, today_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    assert mock_send.call_count == 1
    row = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["type"] == "D-0"


def test_check_d0_admin_receives_keyboard(conn, monkeypatch):
    from telegram import InlineKeyboardMarkup
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean AC", 30, today_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    admin_call = mock_send.call_args_list[0]
    reply_markup_arg = admin_call.kwargs.get("reply_markup")
    assert reply_markup_arg is not None
    assert isinstance(reply_markup_arg, InlineKeyboardMarkup)


def test_check_d0_members_receive_no_keyboard(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean AC", 30, today_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    # calls[1:] are member calls — none should have reply_markup
    for member_call in mock_send.call_args_list[1:]:
        assert member_call.kwargs.get("reply_markup") is None


def test_check_d0_skips_when_already_sent(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, today_str())
    # Pre-insert D-0 row for today
    sent_at = today_str() + "T10:00:00Z"
    conn.execute(
        "INSERT INTO REMINDER_LOG (task_id, type, sent_at) VALUES (?, ?, ?)",
        (task_id, "D-0", sent_at),
    )
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    mock_send.assert_not_called()


def test_check_d0_skips_when_task_changed(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, today_str())
    task = task_repo.get_task_by_id(conn, task_id)

    # Simulate task's next_due_date updated after fetch
    conn.execute(
        "UPDATE TASK SET next_due_date=? WHERE id=?",
        ("2026-12-31", task_id),
    )
    conn.commit()

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)  # task still has old due_date

    mock_send.assert_not_called()
    row = conn.execute("SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is None


def test_check_d0_no_log_on_admin_send_failure(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, today_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch(
        "homekeeper.scheduler.loop.sender.send_telegram_message",
        side_effect=Exception("network error"),
    ):
        _check_d0(conn, task)

    row = conn.execute("SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is None


def test_check_d0_continues_on_member_failure(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, today_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    attempt_count = 0

    def send_side_effect(chat_id, text, reply_markup=None):
        nonlocal attempt_count
        attempt_count += 1
        if chat_id == 111:
            raise Exception("member 111 unreachable")

    with patch(
        "homekeeper.scheduler.loop.sender.send_telegram_message",
        side_effect=send_side_effect,
    ):
        _check_d0(conn, task)

    # All 3 attempted: admin + 2 members
    assert attempt_count == 3
    # REMINDER_LOG still written (admin succeeded)
    row = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["type"] == "D-0"


def test_check_d0_sends_to_admin_and_all_members(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, today_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    # 1 admin + 2 members = 3 calls
    assert mock_send.call_count == 3
    called_chat_ids = [c[0][0] for c in mock_send.call_args_list]
    assert 999 in called_chat_ids
    assert 111 in called_chat_ids
    assert 222 in called_chat_ids


def test_check_d0_callback_data_contains_task_id_and_due_date(conn, monkeypatch):
    from telegram import InlineKeyboardMarkup
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "Clean AC", 30, due)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    admin_call = mock_send.call_args_list[0]
    markup = admin_call.kwargs.get("reply_markup")
    assert isinstance(markup, InlineKeyboardMarkup)
    buttons = markup.inline_keyboard[0]
    assert buttons[0].callback_data == f"done:{task_id}:{due}"
    assert buttons[1].callback_data == f"skip:{task_id}:{due}"
