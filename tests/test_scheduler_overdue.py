"""Tests for _check_overdue and related _tick/_check_d0 changes (Story 2.5)."""

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import call, patch

import pytest

from homekeeper.db import reminder_log_repo, task_repo
from homekeeper.scheduler.loop import _check_overdue, _check_d0, _tick

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


def yesterday_str() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def two_days_ago() -> str:
    return (date.today() - timedelta(days=2)).isoformat()


def make_vn_time(hour: int, minute: int = 0) -> datetime:
    vn_tz = timezone(timedelta(hours=7))
    return datetime(2026, 6, 29, hour, minute, 0, tzinfo=vn_tz)


# ---------------------------------------------------------------------------
# _check_overdue unit tests
# ---------------------------------------------------------------------------


def test_check_overdue_sends_when_overdue(conn, monkeypatch):
    """Overdue task with no prior overdue row → sends and logs."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "Clean AC", 30, yesterday_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    assert mock_send.call_count == 1
    row = conn.execute(
        "SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row is not None
    assert row["type"] == "overdue"


def test_check_overdue_skips_if_not_overdue(conn, monkeypatch):
    """Task due today is NOT overdue — skip."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    mock_send.assert_not_called()


def test_check_overdue_skips_future_task(conn, monkeypatch):
    """Task due tomorrow is not overdue — skip."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    task_id = task_repo.create_task(conn, "T", 30, tomorrow)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    mock_send.assert_not_called()


def test_check_overdue_respects_1_hour_gate(conn, monkeypatch):
    """Overdue sent 30 minutes ago → skip (1-hour gate)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    # Insert overdue row 30 minutes ago
    recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "overdue", recent)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    mock_send.assert_not_called()


def test_check_overdue_fires_after_1_hour(conn, monkeypatch):
    """Overdue sent 61 minutes ago → sends (gate passed)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    old = (datetime.now(timezone.utc) - timedelta(minutes=61)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "overdue", old)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    assert mock_send.call_count >= 1


def test_check_overdue_no_log_on_admin_failure(conn, monkeypatch):
    """Admin send fails → no REMINDER_LOG row written."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch(
        "homekeeper.scheduler.loop.sender.send_telegram_message",
        side_effect=Exception("network error"),
    ):
        _check_overdue(conn, task)

    row = conn.execute(
        "SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row is None


def test_check_overdue_admin_receives_keyboard(conn, monkeypatch):
    """Admin overdue message has inline keyboard."""
    from telegram import InlineKeyboardMarkup
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    admin_call = mock_send.call_args_list[0]
    markup = admin_call.kwargs.get("reply_markup")
    assert markup is not None
    assert isinstance(markup, InlineKeyboardMarkup)


def test_check_overdue_members_receive_no_keyboard(conn, monkeypatch):
    """Member overdue messages have no keyboard."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    member_call = mock_send.call_args_list[1]
    assert member_call.kwargs.get("reply_markup") is None


def test_check_overdue_member_text_truncated(conn, monkeypatch):
    """Member overdue message omits 'Bạn đã xử lý chưa?' (AC-1: members get plain form)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.commit()
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    admin_text = mock_send.call_args_list[0][0][1]
    member_text = mock_send.call_args_list[1][0][1]
    assert "Bạn đã xử lý chưa?" in admin_text
    assert "Bạn đã xử lý chưa?" not in member_text
    assert "ngày" in member_text  # still mentions days


def test_check_overdue_catchup_row_blocks_within_1_hour(conn, monkeypatch):
    """A recent 'catchup' row (< 1h ago) blocks overdue from firing (P4 patch)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "catchup", recent)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    mock_send.assert_not_called()


def test_check_overdue_message_mentions_days(conn, monkeypatch):
    """Overdue message includes 'ngày' (days)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    text = mock_send.call_args_list[0][0][1]
    assert "ngày" in text
    assert "⚠️" in text


def test_check_overdue_callback_data_format(conn, monkeypatch):
    """Done/skip buttons use done:{task_id}:{due_date} format."""
    from telegram import InlineKeyboardMarkup
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    due = yesterday_str()
    task_id = task_repo.create_task(conn, "T", 30, due)
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    markup = mock_send.call_args_list[0].kwargs["reply_markup"]
    buttons = markup.inline_keyboard[0]
    assert buttons[0].callback_data == f"done:{task_id}:{due}"
    assert buttons[1].callback_data == f"skip:{task_id}:{due}"


def test_check_overdue_skips_when_task_changed(conn, monkeypatch):
    """AD-8 guard: task due_date changed since fetch → skip."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, yesterday_str())
    task = task_repo.get_task_by_id(conn, task_id)
    # Simulate advance (bot confirmed it)
    conn.execute("UPDATE TASK SET next_due_date=? WHERE id=?", ("2099-12-31", task_id))
    conn.commit()

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_overdue(conn, task)

    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# _tick integration — overdue
# ---------------------------------------------------------------------------


def test_tick_sends_overdue_for_past_due_task(conn, monkeypatch):
    """_tick calls _check_overdue for overdue tasks (due < today)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    # 2026-06-28 is the day BEFORE the _now date (2026-06-29), so due < today
    task_repo.create_task(conn, "T", 30, "2026-06-28")

    with patch("homekeeper.scheduler.loop._check_overdue") as mock_overdue, \
         patch("homekeeper.scheduler.loop._check_d0") as mock_d0, \
         patch("homekeeper.scheduler.loop._check_d1") as mock_d1:
        _tick(conn, _now=make_vn_time(9))

    mock_overdue.assert_called_once()


# ---------------------------------------------------------------------------
# _check_d0 idempotency — catchup row blocks D-0
# ---------------------------------------------------------------------------


def test_check_d0_blocked_by_catchup_row(conn, monkeypatch):
    """A 'catchup' row on due_date blocks _check_d0 from re-sending."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    # Simulate catch-up already fired
    reminder_log_repo.log_sent(conn, task_id, "catchup", today_str() + "T07:00:00Z")
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    mock_send.assert_not_called()


def test_check_d0_blocked_by_existing_d0_row(conn, monkeypatch):
    """Existing D-0 row still blocks _check_d0 (regression guard)."""
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")
    task = task_repo.get_task_by_id(conn, task_id)

    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d0(conn, task)

    mock_send.assert_not_called()
