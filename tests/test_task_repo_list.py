"""Tests for get_all_tasks in task_repo (Story 1.3)."""

import sqlite3
from pathlib import Path

import pytest

from homekeeper.db.task_repo import create_task, get_all_tasks


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def test_get_all_tasks_empty(conn):
    rows = get_all_tasks(conn)
    assert rows == []


def test_get_all_tasks_single(conn):
    create_task(conn, "Thay lõi lọc nước", 90, "2026-07-01")
    rows = get_all_tasks(conn)
    assert len(rows) == 1
    assert rows[0]["name"] == "Thay lõi lọc nước"
    assert rows[0]["next_due_date"] == "2026-07-01"
    assert rows[0]["cycle_days"] == 90


def test_get_all_tasks_sorted_by_next_due_date_asc(conn):
    create_task(conn, "Task C", 30, "2026-09-01")
    create_task(conn, "Task A", 30, "2026-07-01")
    create_task(conn, "Task B", 30, "2026-08-01")
    rows = get_all_tasks(conn)
    assert len(rows) == 3
    assert rows[0]["name"] == "Task A"
    assert rows[1]["name"] == "Task B"
    assert rows[2]["name"] == "Task C"


def test_get_all_tasks_same_date_ordered_by_id(conn):
    create_task(conn, "Task X", 30, "2026-07-01")
    create_task(conn, "Task Y", 60, "2026-07-01")
    rows = get_all_tasks(conn)
    assert len(rows) == 2
    dates = [r["next_due_date"] for r in rows]
    assert all(d == "2026-07-01" for d in dates)
    # same date → secondary sort by id ASC; Task X was inserted first so id is lower
    assert rows[0]["name"] == "Task X"
    assert rows[1]["name"] == "Task Y"


def test_get_all_tasks_row_has_all_columns(conn):
    create_task(conn, "Vệ sinh điều hòa", 180, "2026-12-31")
    rows = get_all_tasks(conn)
    row = rows[0]
    assert row["id"] is not None
    assert row["name"] == "Vệ sinh điều hòa"
    assert row["cycle_days"] == 180
    assert row["next_due_date"] == "2026-12-31"
    assert row["created_at"] is not None
