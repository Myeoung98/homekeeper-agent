import sqlite3


def get_all_members(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT id, telegram_user_id, name FROM MEMBER ORDER BY id ASC")
    return cursor.fetchall()


def get_member_by_id(conn: sqlite3.Connection, member_id: int):
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER WHERE id = ?",
        (member_id,),
    )
    return cursor.fetchone()


def get_member_by_telegram_id(conn: sqlite3.Connection, telegram_user_id: int):
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER WHERE telegram_user_id = ?",
        (telegram_user_id,),
    )
    return cursor.fetchone()


def add_member(conn: sqlite3.Connection, telegram_user_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)",
        (telegram_user_id, name),
    )
    conn.commit()


def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    conn.execute("DELETE FROM MEMBER WHERE id = ?", (member_id,))
    conn.commit()
