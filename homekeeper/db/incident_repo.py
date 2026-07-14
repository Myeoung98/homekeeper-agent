import sqlite3
from datetime import datetime, timezone


def create_incident(
    conn: sqlite3.Connection,
    reported_by: int,
    description: str,
    household_id: int = 0,
) -> int:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "INSERT INTO INCIDENT (reported_by, description, created_at, household_id) "
        "VALUES (?, ?, ?, ?)",
        (reported_by, description, created_at, household_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_incident_by_id(
    conn: sqlite3.Connection,
    incident_id: int,
    household_id: int = 0,
):
    cursor = conn.execute(
        "SELECT id, reported_by, description, created_at FROM INCIDENT "
        "WHERE id = ? AND household_id = ?",
        (incident_id, household_id),
    )
    return cursor.fetchone()
