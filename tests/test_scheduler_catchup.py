"""Tests for scheduler/catchup.py — run_catchup (Story 2.5 Task 4)."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from homekeeper.db import reminder_log_repo, task_repo


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


def yesterday_str() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# run_catchup tests
# ---------------------------------------------------------------------------


def test_catchup_skips_future_tasks(conn, monkeypatch):
    """Task due tomorrow is not yet due — no send."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "Future Task", 30, tomorrow_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    mock_send.assert_not_called()


def test_catchup_sends_for_due_today_no_log(conn, monkeypatch):
    """Task due today with no REMINDER_LOG row → sends and writes 'catchup' row."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Today Task", 30, today_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message"):
        run_catchup(conn)

    row = conn.execute(
        "SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row is not None
    assert row["type"] == "catchup"


def test_catchup_sends_for_overdue_no_log(conn, monkeypatch):
    """Overdue task with no log row → sends catch-up."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "Overdue Task", 30, yesterday_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    assert mock_send.call_count >= 1


def test_catchup_skips_when_any_row_exists(conn, monkeypatch):
    """If any REMINDER_LOG row exists on due_date → skip (D-0 or catchup already sent)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    # Simulate prior D-0 send
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    mock_send.assert_not_called()


def test_catchup_skips_when_catchup_row_exists(conn, monkeypatch):
    """If a 'catchup' row already exists on due_date → skip (idempotent)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "catchup", today_str() + "T07:00:00Z")

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    mock_send.assert_not_called()


def test_catchup_admin_receives_keyboard(conn, monkeypatch):
    """Admin catch-up message includes inline keyboard."""
    from telegram import InlineKeyboardMarkup

    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, today_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    admin_call = mock_send.call_args_list[0]
    markup = admin_call.kwargs.get("reply_markup")
    assert markup is not None
    assert isinstance(markup, InlineKeyboardMarkup)


def test_catchup_members_receive_message(conn, monkeypatch):
    """Members receive a catch-up message (no keyboard)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, today_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Bob"))
    conn.commit()

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    # call_count: 1 admin + 1 member = 2
    assert mock_send.call_count == 2
    member_call = mock_send.call_args_list[1]
    assert member_call.kwargs.get("reply_markup") is None


def test_catchup_handles_admin_send_failure_gracefully(conn, monkeypatch):
    """Admin send fails → no REMINDER_LOG row, no crash."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch(
        "homekeeper.scheduler.catchup.sender.send_telegram_message",
        side_effect=Exception("network error"),
    ):
        run_catchup(conn)  # must not raise

    row = conn.execute(
        "SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row is None


def test_catchup_message_includes_label(conn, monkeypatch):
    """Catch-up message text includes the 'Gửi bù' label."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_repo.create_task(conn, "T", 30, today_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    text = mock_send.call_args_list[0][0][1]
    assert "Gửi bù" in text


def test_catchup_logs_catchup_type(conn, monkeypatch):
    """run_catchup writes REMINDER_LOG row with type='catchup'."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message"):
        run_catchup(conn)

    row = conn.execute(
        "SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row is not None
    assert row["type"] == "catchup"


def test_catchup_callback_data_format(conn, monkeypatch):
    """Done/skip buttons use done:{task_id}:{due_date} format."""
    from telegram import InlineKeyboardMarkup

    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = today_str()
    task_id = task_repo.create_task(conn, "T", 30, due)

    from homekeeper.scheduler.catchup import run_catchup

    with patch("homekeeper.scheduler.catchup.sender.send_telegram_message") as mock_send:
        run_catchup(conn)

    markup = mock_send.call_args_list[0].kwargs["reply_markup"]
    buttons = markup.inline_keyboard[0]
    assert buttons[0].callback_data == f"done:{task_id}:{due}"
    assert buttons[1].callback_data == f"skip:{task_id}:{due}"
