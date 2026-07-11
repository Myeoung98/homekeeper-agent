import sqlite3
from datetime import datetime, timezone


def get_all_tasks(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK ORDER BY next_due_date ASC, id ASC"
    )
    return cursor.fetchall()


def create_task(
    conn: sqlite3.Connection,
    name: str,
    cycle_days: int,
    next_due_date: str,
) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at) VALUES (?, ?, ?, ?)",
        (name, cycle_days, next_due_date, now),
    )
    conn.commit()
    return cursor.lastrowid


def get_task_by_id(conn: sqlite3.Connection, task_id: int):
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK WHERE id = ?",
        (task_id,),
    )
    return cursor.fetchone()


def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    name: str,
    cycle_days: int,
    next_due_date: str,
) -> None:
    conn.execute(
        "UPDATE TASK SET name = ?, cycle_days = ?, next_due_date = ? WHERE id = ?",
        (name, cycle_days, next_due_date, task_id),
    )
    conn.commit()


def delete_task(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM TASK WHERE id = ?", (task_id,))
    conn.commit()


def advance_next_due_date(conn: sqlite3.Connection, task_id: int, new_due_date: str) -> None:
    """Update only next_due_date for the given task.
    Single-writer constraint: only bot/reminder_callbacks.py should call this (AD-8).
    """
    conn.execute("UPDATE TASK SET next_due_date=? WHERE id=?", (new_due_date, task_id))
    conn.commit()
