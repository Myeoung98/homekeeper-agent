"""Tests for DB helper functions added in Story 2.4:
confirm_reminder (reminder_log_repo) and advance_next_due_date (task_repo).
"""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

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


# ---------------------------------------------------------------------------
# confirm_reminder
# ---------------------------------------------------------------------------


def test_confirm_reminder_updates_confirmed_at(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    sent_at = today_str() + "T08:00:00Z"
    reminder_log_repo.log_sent(conn, task_id, "D-0", sent_at)

    confirmed_at = today_str() + "T10:00:00Z"
    rowcount = reminder_log_repo.confirm_reminder(conn, task_id, "D-0", today_str(), confirmed_at)

    assert rowcount == 1
    row = conn.execute(
        "SELECT confirmed_at FROM REMINDER_LOG WHERE task_id=?", (task_id,)
    ).fetchone()
    assert row["confirmed_at"] == confirmed_at


def test_confirm_reminder_returns_zero_if_no_matching_row(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    # No REMINDER_LOG row exists
    rowcount = reminder_log_repo.confirm_reminder(conn, task_id, "D-0", today_str(), today_str() + "T10:00:00Z")
    assert rowcount == 0


def test_confirm_reminder_does_not_affect_other_rows(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Two rows: D-0 today and D-1 yesterday
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")
    reminder_log_repo.log_sent(conn, task_id, "D-1", yesterday + "T08:00:00Z")

    confirmed_at = today_str() + "T10:00:00Z"
    reminder_log_repo.confirm_reminder(conn, task_id, "D-0", today_str(), confirmed_at)

    d1_row = conn.execute(
        "SELECT confirmed_at FROM REMINDER_LOG WHERE task_id=? AND type='D-1'", (task_id,)
    ).fetchone()
    assert d1_row["confirmed_at"] is None


# ---------------------------------------------------------------------------
# advance_next_due_date
# ---------------------------------------------------------------------------


def test_advance_next_due_date_updates_task(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    new_due = (date.today() + timedelta(days=30)).isoformat()

    task_repo.advance_next_due_date(conn, task_id, new_due)

    row = task_repo.get_task_by_id(conn, task_id)
    assert row["next_due_date"] == new_due


def test_advance_next_due_date_does_not_change_cycle_or_name(conn):
    task_id = task_repo.create_task(conn, "Clean Filter", 90, today_str())
    new_due = (date.today() + timedelta(days=90)).isoformat()

    task_repo.advance_next_due_date(conn, task_id, new_due)

    row = task_repo.get_task_by_id(conn, task_id)
    assert row["name"] == "Clean Filter"
    assert row["cycle_days"] == 90


def test_advance_next_due_date_no_op_on_missing_id(conn):
    # Should not raise even if task_id doesn't exist
    task_repo.advance_next_due_date(conn, 9999, today_str())
