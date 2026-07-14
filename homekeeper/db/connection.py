import os
import sqlite3
from pathlib import Path


def open_db() -> sqlite3.Connection:
    """Open a new SQLite connection for the calling thread.

    Enables WAL mode, enforces FK constraints, and runs schema.sql
    (idempotent CREATE TABLE IF NOT EXISTS).
    Call once per thread — never share the returned connection across threads (AD-5).
    """
    db_path = os.environ["DB_PATH"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)  # check_same_thread=True (default) enforces AD-5
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent / "schema.sql"
    conn.executescript(schema.read_text())
    # Migration: add household_id to existing tables (idempotent — column already exists is ok)
    for stmt in [
        "ALTER TABLE TASK ADD COLUMN household_id INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE MEMBER ADD COLUMN household_id INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE REPAIRMAN ADD COLUMN household_id INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE INCIDENT ADD COLUMN household_id INTEGER NOT NULL DEFAULT 0",
    ]:
        try:
            conn.execute(stmt)
            conn.commit()
        except sqlite3.OperationalError:
            pass
    return conn
