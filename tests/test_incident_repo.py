import sqlite3
from pathlib import Path

import pytest

from homekeeper.db import incident_repo


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()


def test_create_incident_returns_id(conn):
    incident_id = incident_repo.create_incident(conn, reported_by=111, description="Quạt hỏng")
    assert isinstance(incident_id, int)
    assert incident_id >= 1


def test_create_incident_persists_reported_by(conn):
    incident_repo.create_incident(conn, reported_by=222, description="Điện tripped")
    row = conn.execute("SELECT reported_by FROM INCIDENT WHERE id=1").fetchone()
    assert row["reported_by"] == 222


def test_create_incident_persists_description(conn):
    incident_repo.create_incident(conn, reported_by=111, description="Ống nước bị vỡ")
    row = conn.execute("SELECT description FROM INCIDENT WHERE id=1").fetchone()
    assert row["description"] == "Ống nước bị vỡ"


def test_create_incident_persists_created_at_utc_format(conn):
    incident_repo.create_incident(conn, reported_by=111, description="Test")
    row = conn.execute("SELECT created_at FROM INCIDENT WHERE id=1").fetchone()
    created_at = row["created_at"]
    # Must be ISO-8601 UTC: YYYY-MM-DDTHH:MM:SSZ
    assert len(created_at) == 20
    assert created_at.endswith("Z")
    assert "T" in created_at


def test_create_incident_sequential_ids(conn):
    id1 = incident_repo.create_incident(conn, reported_by=1, description="First")
    id2 = incident_repo.create_incident(conn, reported_by=2, description="Second")
    assert id2 == id1 + 1


def test_get_incident_by_id_returns_correct_row(conn):
    incident_id = incident_repo.create_incident(conn, reported_by=111, description="Điều hòa hỏng")
    row = incident_repo.get_incident_by_id(conn, incident_id)
    assert row is not None
    assert row["id"] == incident_id
    assert row["reported_by"] == 111


def test_get_incident_by_id_returns_correct_description(conn):
    incident_id = incident_repo.create_incident(conn, reported_by=222, description="Ống nước vỡ")
    row = incident_repo.get_incident_by_id(conn, incident_id)
    assert row["description"] == "Ống nước vỡ"


def test_get_incident_by_id_returns_none_for_missing(conn):
    row = incident_repo.get_incident_by_id(conn, 9999)
    assert row is None
