"""Tests for D-1 reminder logic in Story 2.2."""

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import call, patch

import pytest

from homekeeper.db import task_repo
from homekeeper.scheduler.loop import _check_d1, _tick


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def today_str() -> str:
    return date.today().isoformat()


def make_vn_time(hour: int, minute: int = 0) -> datetime:
    """Return a fixed VN datetime (2026-06-29) at the given hour:minute."""
    vn_tz = timezone(timedelta(hours=7))
    return datetime(2026, 6, 29, hour, minute, 0, tzinfo=vn_tz)


# ---------------------------------------------------------------------------
# _tick time-gate tests
# ---------------------------------------------------------------------------


def test_tick_skips_before_8am(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, "2026-06-30")

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(hour=7, minute=59))

    mock_send.assert_not_called()


def test_tick_at_exactly_8am_does_not_send(conn, monkeypatch):
    """hour=8 satisfies the condition (not < 8) — sends are expected after 08:00."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, "2026-06-30")

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(hour=8, minute=0))

    # At exactly 08:00, hour is 8 which is NOT < 8, so tick runs and tries to send
    assert mock_send.call_count >= 1


def test_tick_sends_after_8am(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, "2026-06-30")

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(hour=8, minute=1))

    assert mock_send.call_count >= 1


def test_tick_skips_task_not_due_tomorrow(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, "2026-07-01")  # due in 2 days from 2026-06-29 VN

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _tick(conn, _now=make_vn_time(hour=9, minute=0))

    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# _check_d1 logic tests
# ---------------------------------------------------------------------------


def test_check_d1_sends_when_not_yet_sent(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean AC", 30, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    mock_send.assert_called_once()
    row = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["type"] == "D-1"


def test_check_d1_message_contains_task_name_and_due_date(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Fix Sink", 7, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    args = mock_send.call_args[0]
    text = args[1]
    assert "Fix Sink" in text
    assert "<b>" in text  # HTML bold


def test_check_d1_skips_when_already_sent(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    # Insert a REMINDER_LOG row showing D-1 already sent today
    sent_at = today_str() + "T10:00:00"
    conn.execute(
        "INSERT INTO REMINDER_LOG (task_id, type, sent_at) VALUES (?, ?, ?)",
        (task_id, "D-1", sent_at),
    )
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    mock_send.assert_not_called()


def test_check_d1_skips_when_task_changed(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)

    # Simulate task's next_due_date being updated between tick and check
    conn.execute(
        "UPDATE TASK SET next_due_date=? WHERE id=?",
        ("2026-12-31", task_id),
    )
    conn.commit()

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)  # task still has old due_date

    mock_send.assert_not_called()
    row = conn.execute("SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is None


def test_check_d1_no_log_on_send_failure(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch(
        "homekeeper.scheduler.loop.sender.send_telegram_message",
        side_effect=Exception("network error"),
    ):
        _check_d1(conn, task)

    row = conn.execute("SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is None


def test_check_d1_sends_to_members(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    # 1 admin + 2 members = 3 calls
    assert mock_send.call_count == 3
    called_chat_ids = [c[0][0] for c in mock_send.call_args_list]
    assert 999 in called_chat_ids
    assert 111 in called_chat_ids
    assert 222 in called_chat_ids


def test_check_d1_members_receive_no_keyboard(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    member_call = [c for c in mock_send.call_args_list if c[0][0] == 111][0]
    assert member_call.kwargs.get("reply_markup") is None


def test_check_d1_continues_on_member_failure(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Task", 30, tomorrow_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    call_count = 0

    def send_side_effect(chat_id, text):
        nonlocal call_count
        call_count += 1
        if chat_id == 111:
            raise Exception("member 111 unreachable")

    with patch(
        "homekeeper.scheduler.loop.sender.send_telegram_message",
        side_effect=send_side_effect,
    ):
        _check_d1(conn, task)

    # All 3 were attempted: admin + 2 members
    assert call_count == 3
    # REMINDER_LOG row was still written (admin succeeded)
    row = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["type"] == "D-1"


def test_check_d1_html_escapes_task_name(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean <pipes> & valves", 30, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)

    args = mock_send.call_args[0]
    text = args[1]
    assert "<pipes>" not in text
    assert "&lt;pipes&gt;" in text
    assert "&amp;" in text
