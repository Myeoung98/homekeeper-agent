import sqlite3


def get_all_repairmen(conn: sqlite3.Connection, household_id: int = 0) -> list:
    cursor = conn.execute(
        "SELECT id, name, phone, service_type FROM REPAIRMAN "
        "WHERE household_id = ? ORDER BY id ASC",
        (household_id,),
    )
    return cursor.fetchall()


def create_repairman(
    conn: sqlite3.Connection,
    name: str,
    phone: str,
    service_type: str,
    household_id: int = 0,
) -> int:
    cursor = conn.execute(
        "INSERT INTO REPAIRMAN (name, phone, service_type, household_id) VALUES (?, ?, ?, ?)",
        (name, phone, service_type, household_id),
    )
    conn.commit()
    return cursor.lastrowid


def get_repairman_by_id(
    conn: sqlite3.Connection,
    repairman_id: int,
    household_id: int = 0,
):
    cursor = conn.execute(
        "SELECT id, name, phone, service_type FROM REPAIRMAN "
        "WHERE id = ? AND household_id = ?",
        (repairman_id, household_id),
    )
    return cursor.fetchone()


def update_repairman(
    conn: sqlite3.Connection,
    repairman_id: int,
    name: str,
    phone: str,
    service_type: str,
    household_id: int = 0,
) -> None:
    conn.execute(
        "UPDATE REPAIRMAN SET name = ?, phone = ?, service_type = ? "
        "WHERE id = ? AND household_id = ?",
        (name, phone, service_type, repairman_id, household_id),
    )
    conn.commit()


def delete_repairman(
    conn: sqlite3.Connection,
    repairman_id: int,
    household_id: int = 0,
) -> None:
    conn.execute(
        "DELETE FROM REPAIRMAN WHERE id = ? AND household_id = ?",
        (repairman_id, household_id),
    )
    conn.commit()
