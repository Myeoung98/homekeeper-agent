import sqlite3


def get_all_members(conn: sqlite3.Connection, household_id: int = 0) -> list:
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER "
        "WHERE household_id = ? ORDER BY id ASC",
        (household_id,),
    )
    return cursor.fetchall()


def get_member_by_id(conn: sqlite3.Connection, member_id: int, household_id: int = 0):
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER WHERE id = ? AND household_id = ?",
        (member_id, household_id),
    )
    return cursor.fetchone()


def get_member_by_telegram_id(
    conn: sqlite3.Connection,
    telegram_user_id: int,
    household_id: int = 0,
):
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER "
        "WHERE telegram_user_id = ? AND household_id = ?",
        (telegram_user_id, household_id),
    )
    return cursor.fetchone()


def add_member(
    conn: sqlite3.Connection,
    telegram_user_id: int,
    name: str,
    household_id: int = 0,
) -> None:
    conn.execute(
        "INSERT INTO MEMBER (telegram_user_id, name, household_id) VALUES (?, ?, ?)",
        (telegram_user_id, name, household_id),
    )
    conn.commit()


def delete_member(conn: sqlite3.Connection, member_id: int, household_id: int = 0) -> None:
    conn.execute("DELETE FROM MEMBER WHERE id = ? AND household_id = ?", (member_id, household_id))
    conn.commit()
