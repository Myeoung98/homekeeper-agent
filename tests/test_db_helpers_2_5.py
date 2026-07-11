"""Unit tests for reminder_log_repo helpers added in Story 2.5."""

import sqlite3
from datetime import date, datetime, timezone
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
# get_latest_sent_at
# ---------------------------------------------------------------------------


def test_get_latest_sent_at_returns_none_when_no_rows(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    result = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    assert result is None


def test_get_latest_sent_at_returns_value_when_row_exists(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    sent_at = today_str() + "T08:00:00Z"
    reminder_log_repo.log_sent(conn, task_id, "overdue", sent_at)
    result = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    assert result == sent_at


def test_get_latest_sent_at_returns_most_recent(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "overdue", today_str() + "T08:00:00Z")
    later = today_str() + "T09:00:00Z"
    reminder_log_repo.log_sent(conn, task_id, "overdue", later)
    result = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    assert result == later


def test_get_latest_sent_at_filters_by_type(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")
    result = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    assert result is None


# ---------------------------------------------------------------------------
# any_sent_on_date
# ---------------------------------------------------------------------------


def test_any_sent_on_date_false_when_no_rows(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    assert reminder_log_repo.any_sent_on_date(conn, task_id, today_str()) is False


def test_any_sent_on_date_true_for_d0_row(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")
    assert reminder_log_repo.any_sent_on_date(conn, task_id, today_str()) is True


def test_any_sent_on_date_true_for_catchup_row(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "catchup", today_str() + "T08:00:00Z")
    assert reminder_log_repo.any_sent_on_date(conn, task_id, today_str()) is True


def test_any_sent_on_date_false_for_different_date(conn):
    task_id = task_repo.create_task(conn, "T", 30, today_str())
    reminder_log_repo.log_sent(conn, task_id, "D-0", today_str() + "T08:00:00Z")
    assert reminder_log_repo.any_sent_on_date(conn, task_id, "2099-01-01") is False
