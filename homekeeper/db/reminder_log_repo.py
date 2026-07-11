import sqlite3


def already_sent(conn: sqlite3.Connection, task_id: int, reminder_type: str, sent_date: str) -> bool:
    """Return True if a reminder of the given type was sent on sent_date for this task.

    sent_date is YYYY-MM-DD of the calendar day the reminder is expected to fire.
    For D-1: pass (due_date - 1 day). For D-0: pass due_date.
    Uses SQLite date() to extract the calendar date from the stored UTC datetime.
    """
    row = conn.execute(
        "SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND type=? AND date(sent_at)=? LIMIT 1",
        (task_id, reminder_type, sent_date),
    ).fetchone()
    return row is not None


def log_sent(conn: sqlite3.Connection, task_id: int, reminder_type: str, sent_at: str) -> int:
    """Insert a REMINDER_LOG row. sent_at is ISO-8601 UTC datetime. Returns new row id."""
    cursor = conn.execute(
        "INSERT INTO REMINDER_LOG (task_id, type, sent_at) VALUES (?, ?, ?)",
        (task_id, reminder_type, sent_at),
    )
    conn.commit()
    return cursor.lastrowid


def get_latest_sent_at(
    conn: sqlite3.Connection,
    task_id: int,
    reminder_type: str,
) -> str | None:
    """Return the most recent sent_at for this task/type, or None if never sent."""
    row = conn.execute(
        "SELECT sent_at FROM REMINDER_LOG WHERE task_id=? AND type=? "
        "ORDER BY sent_at DESC LIMIT 1",
        (task_id, reminder_type),
    ).fetchone()
    return row["sent_at"] if row else None


def any_sent_on_date(
    conn: sqlite3.Connection,
    task_id: int,
    sent_date: str,
) -> bool:
    """Return True if any reminder (any type) was sent for this task on sent_date.

    sent_date is YYYY-MM-DD. Used by catchup.py (skip check) and _check_d0 (block re-send).
    """
    row = conn.execute(
        "SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND date(sent_at)=? LIMIT 1",
        (task_id, sent_date),
    ).fetchone()
    return row is not None


def confirm_reminder(
    conn: sqlite3.Connection,
    task_id: int,
    reminder_type: str,
    sent_date: str,
    confirmed_at: str,
) -> int:
    """Mark the matching REMINDER_LOG row as confirmed (done or skip).

    sent_date is YYYY-MM-DD — same value passed to already_sent (for D-0: == due_date).
    Returns rowcount (0 means no matching row; caller may log if needed).
    """
    cursor = conn.execute(
        "UPDATE REMINDER_LOG SET confirmed_at=? "
        "WHERE task_id=? AND type=? AND date(sent_at)=?",
        (confirmed_at, task_id, reminder_type, sent_date),
    )
    conn.commit()
    return cursor.rowcount
