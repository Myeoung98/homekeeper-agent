"""Tests for member_repo (Story 2.2 read-only; Story 4.1 adds write functions)."""

import sqlite3
from pathlib import Path

import pytest

from homekeeper.db import member_repo


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def test_get_all_members_empty(conn):
    assert member_repo.get_all_members(conn) == []


def test_get_all_members_returns_all(conn):
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "Alice"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (222, "Bob"))
    conn.commit()
    members = member_repo.get_all_members(conn)
    assert len(members) == 2
    ids = [m["telegram_user_id"] for m in members]
    assert 111 in ids and 222 in ids


def test_get_all_members_ordered_by_id(conn):
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (333, "C"))
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)", (111, "A"))
    conn.commit()
    members = member_repo.get_all_members(conn)
    assert members[0]["telegram_user_id"] == 333  # inserted first → lower id
    assert members[1]["telegram_user_id"] == 111


# ---------------------------------------------------------------------------
# Story 4.1: add_member, get_member_by_telegram_id, delete_member
# ---------------------------------------------------------------------------

def test_add_member_persists_row(conn):
    member_repo.add_member(conn, 111111, "Alice")
    rows = member_repo.get_all_members(conn)
    assert len(rows) == 1
    assert rows[0]["telegram_user_id"] == 111111
    assert rows[0]["name"] == "Alice"


def test_add_member_does_not_raise(conn):
    member_repo.add_member(conn, 222222, "Bob")


def test_add_member_duplicate_raises_integrity_error(conn):
    member_repo.add_member(conn, 333333, "Carol")
    with pytest.raises(sqlite3.IntegrityError):
        member_repo.add_member(conn, 333333, "Carol Again")


def test_get_member_by_telegram_id_returns_correct_row(conn):
    member_repo.add_member(conn, 444444, "Dave")
    row = member_repo.get_member_by_telegram_id(conn, 444444)
    assert row is not None
    assert row["telegram_user_id"] == 444444
    assert row["name"] == "Dave"


def test_get_member_by_telegram_id_returns_none_for_missing(conn):
    result = member_repo.get_member_by_telegram_id(conn, 999999)
    assert result is None


def test_delete_member_removes_row(conn):
    member_repo.add_member(conn, 555555, "Eve")
    row = member_repo.get_member_by_telegram_id(conn, 555555)
    assert row is not None
    member_repo.delete_member(conn, row["id"])
    after = member_repo.get_member_by_telegram_id(conn, 555555)
    assert after is None


def test_delete_member_nonexistent_no_error(conn):
    member_repo.delete_member(conn, 99999)


def test_get_all_members_returns_in_insertion_order(conn):
    member_repo.add_member(conn, 1001, "First")
    member_repo.add_member(conn, 1002, "Second")
    rows = member_repo.get_all_members(conn)
    assert len(rows) == 2
    assert rows[0]["name"] == "First"
    assert rows[1]["name"] == "Second"
