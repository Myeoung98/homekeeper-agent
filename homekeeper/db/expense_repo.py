import sqlite3
from datetime import datetime, timezone


def create_expense(
    conn: sqlite3.Connection,
    amount: int,
    household_id: int = 0,
    task_id: int | None = None,
    incident_id: int | None = None,
    note: str | None = None,
) -> int:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "INSERT INTO EXPENSE (task_id, incident_id, amount, note, created_at, household_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (task_id, incident_id, amount, note, created_at, household_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_monthly_summary(conn: sqlite3.Connection, household_id: int = 0) -> list:
    """Return monthly totals for the last 6 months."""
    rows = conn.execute(
        "SELECT strftime('%Y-%m', created_at) as month, SUM(amount) as total, COUNT(*) as cnt "
        "FROM EXPENSE WHERE household_id = ? "
        "GROUP BY month ORDER BY month DESC LIMIT 6",
        (household_id,),
    ).fetchall()
    return rows


def get_total_this_month(conn: sqlite3.Connection, household_id: int = 0) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM EXPENSE "
        "WHERE household_id = ? AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')",
        (household_id,),
    ).fetchone()
    return row[0] if row else 0
