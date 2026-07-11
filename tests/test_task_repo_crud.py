"""Tests for get_task_by_id, update_task, delete_task in task_repo (Story 1.4)."""

import sqlite3
from pathlib import Path

import pytest

from homekeeper.db.task_repo import (
    create_task,
    delete_task,
    get_task_by_id,
    update_task,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


# ── get_task_by_id ──────────────────────────────────────────────────────────

def test_get_task_by_id_returns_row(conn):
    task_id = create_task(conn, "Thay lõi lọc", 90, "2026-09-01")
    row = get_task_by_id(conn, task_id)
    assert row is not None
    assert row["id"] == task_id
    assert row["name"] == "Thay lõi lọc"
    assert row["cycle_days"] == 90
    assert row["next_due_date"] == "2026-09-01"


def test_get_task_by_id_missing_returns_none(conn):
    result = get_task_by_id(conn, 9999)
    assert result is None


def test_get_task_by_id_returns_correct_row_among_many(conn):
    id1 = create_task(conn, "Task A", 30, "2026-07-01")
    id2 = create_task(conn, "Task B", 60, "2026-08-01")
    row = get_task_by_id(conn, id2)
    assert row["name"] == "Task B"
    assert row["id"] == id2


# ── update_task ─────────────────────────────────────────────────────────────

def test_update_task_changes_all_fields(conn):
    task_id = create_task(conn, "Cũ", 30, "2026-07-01")
    update_task(conn, task_id, "Mới", 60, "2026-10-01")
    row = get_task_by_id(conn, task_id)
    assert row["name"] == "Mới"
    assert row["cycle_days"] == 60
    assert row["next_due_date"] == "2026-10-01"


def test_update_task_does_not_affect_other_rows(conn):
    id1 = create_task(conn, "Task A", 30, "2026-07-01")
    id2 = create_task(conn, "Task B", 60, "2026-08-01")
    update_task(conn, id1, "Updated A", 90, "2026-09-01")
    row2 = get_task_by_id(conn, id2)
    assert row2["name"] == "Task B"
    assert row2["cycle_days"] == 60


def test_update_task_persists_after_fresh_select(conn):
    task_id = create_task(conn, "Before", 30, "2026-07-01")
    update_task(conn, task_id, "After", 45, "2026-11-15")
    row = get_task_by_id(conn, task_id)
    assert row["name"] == "After"
    assert row["next_due_date"] == "2026-11-15"


# ── delete_task ─────────────────────────────────────────────────────────────

def test_delete_task_removes_row(conn):
    task_id = create_task(conn, "To Delete", 30, "2026-07-01")
    delete_task(conn, task_id)
    assert get_task_by_id(conn, task_id) is None


def test_delete_task_does_not_affect_other_rows(conn):
    id1 = create_task(conn, "Task A", 30, "2026-07-01")
    id2 = create_task(conn, "Task B", 60, "2026-08-01")
    delete_task(conn, id1)
    assert get_task_by_id(conn, id2) is not None
    assert get_task_by_id(conn, id2)["name"] == "Task B"


def test_delete_task_nonexistent_is_silent(conn):
    delete_task(conn, 9999)  # should not raise
