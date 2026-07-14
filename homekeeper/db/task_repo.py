import sqlite3
from datetime import datetime, timezone


def get_all_tasks(conn: sqlite3.Connection, household_id: int = 0) -> list:
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK WHERE household_id = ? ORDER BY next_due_date ASC, id ASC",
        (household_id,),
    )
    return cursor.fetchall()


def create_task(
    conn: sqlite3.Connection,
    name: str,
    cycle_days: int,
    next_due_date: str,
    household_id: int = 0,
) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at, household_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, cycle_days, next_due_date, now, household_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_task_by_id(conn: sqlite3.Connection, task_id: int, household_id: int = 0):
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK WHERE id = ? AND household_id = ?",
        (task_id, household_id),
    )
    return cursor.fetchone()


def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    name: str,
    cycle_days: int,
    next_due_date: str,
    household_id: int = 0,
) -> None:
    conn.execute(
        "UPDATE TASK SET name = ?, cycle_days = ?, next_due_date = ? "
        "WHERE id = ? AND household_id = ?",
        (name, cycle_days, next_due_date, task_id, household_id),
    )
    conn.commit()


def delete_task(conn: sqlite3.Connection, task_id: int, household_id: int = 0) -> None:
    conn.execute("DELETE FROM TASK WHERE id = ? AND household_id = ?", (task_id, household_id))
    conn.commit()


def advance_next_due_date(
    conn: sqlite3.Connection,
    task_id: int,
    new_due_date: str,
    household_id: int = 0,
) -> None:
    """Update only next_due_date for the given task.
    Single-writer constraint: only bot/reminder_callbacks.py should call this (AD-8).
    """
    conn.execute(
        "UPDATE TASK SET next_due_date=? WHERE id=? AND household_id=?",
        (new_due_date, task_id, household_id),
    )
    conn.commit()
