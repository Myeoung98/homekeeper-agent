import sqlite3
from datetime import datetime, timezone


def add_rating(
    conn: sqlite3.Connection,
    repairman_id: int,
    stars: int,
    household_id: int = 0,
    incident_id: int | None = None,
) -> int:
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor = conn.execute(
        "INSERT INTO REPAIRMAN_RATING (repairman_id, incident_id, stars, created_at, household_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (repairman_id, incident_id, stars, created_at, household_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_avg_rating(
    conn: sqlite3.Connection,
    repairman_id: int,
    household_id: int = 0,
) -> tuple[float | None, int]:
    """Return (avg_stars, count). avg is None if no ratings."""
    row = conn.execute(
        "SELECT AVG(stars), COUNT(*) FROM REPAIRMAN_RATING "
        "WHERE repairman_id = ? AND household_id = ?",
        (repairman_id, household_id),
    ).fetchone()
    avg = round(row[0], 1) if row and row[0] is not None else None
    count = row[1] if row else 0
    return avg, count
