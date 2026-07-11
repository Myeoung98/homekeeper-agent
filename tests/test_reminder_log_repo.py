"""Tests for reminder_log_repo (Story 2.2)."""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import pytest

from homekeeper.db.task_repo import create_task


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


@pytest.fixture
def task_id(conn):
    return create_task(conn, "Thay lọc nước", 30, "2026-07-01")


# ── already_sent ─────────────────────────────────────────────────────────────

def test_already_sent_false_when_no_rows(conn, task_id):
    from homekeeper.db.reminder_log_repo import already_sent
    assert already_sent(conn, task_id, "D-1", "2026-06-30") is False


def test_already_sent_true_when_row_exists(conn, task_id):
    from homekeeper.db.reminder_log_repo import already_sent, log_sent
    log_sent(conn, task_id, "D-1", "2026-06-30T01:05:00")
    assert already_sent(conn, task_id, "D-1", "2026-06-30") is True


def test_already_sent_false_when_date_differs(conn, task_id):
    from homekeeper.db.reminder_log_repo import already_sent, log_sent
    log_sent(conn, task_id, "D-1", "2026-06-30T01:05:00")
    assert already_sent(conn, task_id, "D-1", "2026-06-29") is False


def test_already_sent_false_when_type_differs(conn, task_id):
    from homekeeper.db.reminder_log_repo import already_sent, log_sent
    log_sent(conn, task_id, "D-0", "2026-06-30T01:05:00")
    assert already_sent(conn, task_id, "D-1", "2026-06-30") is False


def test_already_sent_false_when_task_id_differs(conn, task_id):
    from homekeeper.db.reminder_log_repo import already_sent, log_sent
    other_task_id = create_task(conn, "Other", 30, "2026-07-01")
    log_sent(conn, other_task_id, "D-1", "2026-06-30T01:05:00")
    assert already_sent(conn, task_id, "D-1", "2026-06-30") is False


# ── log_sent ──────────────────────────────────────────────────────────────────

def test_log_sent_creates_row(conn, task_id):
    from homekeeper.db.reminder_log_repo import log_sent
    log_sent(conn, task_id, "D-1", "2026-06-30T01:05:00")
    row = conn.execute("SELECT * FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row is not None
    assert row["type"] == "D-1"
    assert row["sent_at"] == "2026-06-30T01:05:00"
    assert row["confirmed_at"] is None


def test_log_sent_returns_positive_id(conn, task_id):
    from homekeeper.db.reminder_log_repo import log_sent
    row_id = log_sent(conn, task_id, "D-1", "2026-06-30T01:05:00")
    assert isinstance(row_id, int)
    assert row_id > 0


def test_log_sent_multiple_types(conn, task_id):
    from homekeeper.db.reminder_log_repo import log_sent
    log_sent(conn, task_id, "D-1", "2026-06-30T01:05:00")
    log_sent(conn, task_id, "D-0", "2026-07-01T01:05:00")
    rows = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
    assert [r["type"] for r in rows] == ["D-1", "D-0"]
