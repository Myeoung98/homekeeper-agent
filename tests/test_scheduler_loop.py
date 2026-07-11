"""Tests for scheduler loop infrastructure (Story 2.1)."""

import logging
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from homekeeper.scheduler.loop import _run_loop, _task_unchanged, _tick, start_scheduler
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


# ── _tick ────────────────────────────────────────────────────────────────────

def test_run_loop_exits_on_db_open_failure(caplog):
    with patch("homekeeper.scheduler.loop.open_db", side_effect=RuntimeError("no DB")):
        with caplog.at_level(logging.ERROR, logger="homekeeper.scheduler.loop"):
            _run_loop()
    assert "Scheduler failed to open DB" in caplog.text


# ── _tick ────────────────────────────────────────────────────────────────────

def test_tick_does_not_raise_empty_db(conn):
    _tick(conn)


def test_tick_does_not_raise_with_tasks(conn):
    create_task(conn, "Thay lọc nước", 30, "2099-07-01")
    _tick(conn)


def test_tick_logs_debug(conn, caplog):
    with caplog.at_level(logging.DEBUG, logger="homekeeper.scheduler.loop"):
        _tick(conn)
    assert "Scheduler tick" in caplog.text


# ── _task_unchanged ───────────────────────────────────────────────────────────

def test_task_unchanged_true_when_date_matches(conn):
    task_id = create_task(conn, "Task", 30, "2099-07-01")
    assert _task_unchanged(conn, task_id, "2099-07-01") is True


def test_task_unchanged_false_when_date_differs(conn):
    task_id = create_task(conn, "Task", 30, "2099-07-01")
    assert _task_unchanged(conn, task_id, "2099-08-01") is False


def test_task_unchanged_false_when_task_missing(conn):
    assert _task_unchanged(conn, 9999, "2099-07-01") is False


# ── start_scheduler ───────────────────────────────────────────────────────────

def test_start_scheduler_returns_daemon_thread():
    with patch("homekeeper.scheduler.loop._run_loop"):
        t = start_scheduler()
    assert t.daemon is True


def test_start_scheduler_thread_name():
    with patch("homekeeper.scheduler.loop._run_loop"):
        t = start_scheduler()
    assert t.name == "scheduler"


def test_start_scheduler_calls_run_loop():
    called = threading.Event()

    def fake_run_loop():
        called.set()

    with patch("homekeeper.scheduler.loop._run_loop", side_effect=fake_run_loop):
        start_scheduler()
    assert called.wait(timeout=2.0)
