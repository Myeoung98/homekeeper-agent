"""Tests for homekeeper/db/repairman_repo.py (Story 3.1)."""

import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


# ---------------------------------------------------------------------------
# get_all_repairmen
# ---------------------------------------------------------------------------


def test_get_all_repairmen_empty(conn):
    from homekeeper.db.repairman_repo import get_all_repairmen
    assert get_all_repairmen(conn) == []


def test_get_all_repairmen_returns_all(conn):
    from homekeeper.db.repairman_repo import create_repairman, get_all_repairmen
    create_repairman(conn, "Thợ A", "0901234567", "điều hòa")
    create_repairman(conn, "Thợ B", "0912345678", "điện lạnh")
    rows = get_all_repairmen(conn)
    assert len(rows) == 2


def test_get_all_repairmen_ordered_by_id(conn):
    from homekeeper.db.repairman_repo import create_repairman, get_all_repairmen
    create_repairman(conn, "First", "0900000001", "plumbing")
    create_repairman(conn, "Second", "0900000002", "electric")
    rows = get_all_repairmen(conn)
    assert rows[0]["name"] == "First"
    assert rows[1]["name"] == "Second"


def test_get_all_repairmen_fields(conn):
    from homekeeper.db.repairman_repo import create_repairman, get_all_repairmen
    create_repairman(conn, "Nguyễn Văn A", "0909090909", "điều hòa, tủ lạnh")
    row = get_all_repairmen(conn)[0]
    assert row["name"] == "Nguyễn Văn A"
    assert row["phone"] == "0909090909"
    assert row["service_type"] == "điều hòa, tủ lạnh"


# ---------------------------------------------------------------------------
# create_repairman
# ---------------------------------------------------------------------------


def test_create_repairman_returns_id(conn):
    from homekeeper.db.repairman_repo import create_repairman
    rid = create_repairman(conn, "Thợ X", "0900000000", "plumbing")
    assert isinstance(rid, int)
    assert rid > 0


def test_create_repairman_persisted(conn):
    from homekeeper.db.repairman_repo import create_repairman
    create_repairman(conn, "Thợ X", "0900000000", "plumbing")
    row = conn.execute("SELECT * FROM REPAIRMAN").fetchone()
    assert row["name"] == "Thợ X"
    assert row["phone"] == "0900000000"
    assert row["service_type"] == "plumbing"


# ---------------------------------------------------------------------------
# get_repairman_by_id
# ---------------------------------------------------------------------------


def test_get_repairman_by_id_exists(conn):
    from homekeeper.db.repairman_repo import create_repairman, get_repairman_by_id
    rid = create_repairman(conn, "Thợ Y", "0911111111", "tile")
    row = get_repairman_by_id(conn, rid)
    assert row is not None
    assert row["id"] == rid
    assert row["name"] == "Thợ Y"


def test_get_repairman_by_id_not_found(conn):
    from homekeeper.db.repairman_repo import get_repairman_by_id
    assert get_repairman_by_id(conn, 9999) is None


# ---------------------------------------------------------------------------
# update_repairman
# ---------------------------------------------------------------------------


def test_update_repairman_changes_fields(conn):
    from homekeeper.db.repairman_repo import create_repairman, update_repairman, get_repairman_by_id
    rid = create_repairman(conn, "Old Name", "0900000000", "old service")
    update_repairman(conn, rid, "New Name", "0999999999", "new service")
    row = get_repairman_by_id(conn, rid)
    assert row["name"] == "New Name"
    assert row["phone"] == "0999999999"
    assert row["service_type"] == "new service"


def test_update_repairman_does_not_affect_others(conn):
    from homekeeper.db.repairman_repo import create_repairman, update_repairman, get_repairman_by_id
    rid1 = create_repairman(conn, "Alice", "0900000001", "electric")
    rid2 = create_repairman(conn, "Bob", "0900000002", "plumbing")
    update_repairman(conn, rid1, "Alice Updated", "0900000001", "electric+gas")
    row2 = get_repairman_by_id(conn, rid2)
    assert row2["name"] == "Bob"


# ---------------------------------------------------------------------------
# delete_repairman
# ---------------------------------------------------------------------------


def test_delete_repairman_removes_row(conn):
    from homekeeper.db.repairman_repo import create_repairman, delete_repairman, get_repairman_by_id
    rid = create_repairman(conn, "Thợ Z", "0922222222", "painting")
    delete_repairman(conn, rid)
    assert get_repairman_by_id(conn, rid) is None


def test_delete_repairman_does_not_affect_others(conn):
    from homekeeper.db.repairman_repo import create_repairman, delete_repairman, get_all_repairmen
    rid1 = create_repairman(conn, "Keep", "0900000001", "tile")
    rid2 = create_repairman(conn, "Remove", "0900000002", "paint")
    delete_repairman(conn, rid2)
    rows = get_all_repairmen(conn)
    assert len(rows) == 1
    assert rows[0]["name"] == "Keep"
