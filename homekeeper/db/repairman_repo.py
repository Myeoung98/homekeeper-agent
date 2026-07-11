import sqlite3


def get_all_repairmen(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        "SELECT id, name, phone, service_type FROM REPAIRMAN ORDER BY id ASC"
    )
    return cursor.fetchall()


def create_repairman(
    conn: sqlite3.Connection,
    name: str,
    phone: str,
    service_type: str,
) -> int:
    cursor = conn.execute(
        "INSERT INTO REPAIRMAN (name, phone, service_type) VALUES (?, ?, ?)",
        (name, phone, service_type),
    )
    conn.commit()
    return cursor.lastrowid


def get_repairman_by_id(conn: sqlite3.Connection, repairman_id: int):
    cursor = conn.execute(
        "SELECT id, name, phone, service_type FROM REPAIRMAN WHERE id = ?",
        (repairman_id,),
    )
    return cursor.fetchone()


def update_repairman(
    conn: sqlite3.Connection,
    repairman_id: int,
    name: str,
    phone: str,
    service_type: str,
) -> None:
    conn.execute(
        "UPDATE REPAIRMAN SET name = ?, phone = ?, service_type = ? WHERE id = ?",
        (name, phone, service_type, repairman_id),
    )
    conn.commit()


def delete_repairman(conn: sqlite3.Connection, repairman_id: int) -> None:
    conn.execute("DELETE FROM REPAIRMAN WHERE id = ?", (repairman_id,))
    conn.commit()
