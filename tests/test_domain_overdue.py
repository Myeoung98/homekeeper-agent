"""Unit tests for homekeeper/domain/overdue.py (Story 2.5)."""

from datetime import datetime, timedelta, timezone

import pytest

from homekeeper.domain.overdue import _VN_TZ, days_overdue, hours_overdue, is_overdue


def make_task(due_date: str) -> dict:
    return {"next_due_date": due_date}


def _vn_today():
    return datetime.now(_VN_TZ).date()


def yesterday() -> str:
    return (_vn_today() - timedelta(days=1)).isoformat()


def today_str() -> str:
    return _vn_today().isoformat()


def tomorrow() -> str:
    return (_vn_today() + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# is_overdue
# ---------------------------------------------------------------------------


def test_is_overdue_yesterday():
    assert is_overdue(make_task(yesterday())) is True


def test_is_overdue_two_days_ago():
    two_days_ago = (_vn_today() - timedelta(days=2)).isoformat()
    assert is_overdue(make_task(two_days_ago)) is True


def test_is_overdue_today_is_false():
    assert is_overdue(make_task(today_str())) is False


def test_is_overdue_tomorrow_is_false():
    assert is_overdue(make_task(tomorrow())) is False


# ---------------------------------------------------------------------------
# days_overdue
# ---------------------------------------------------------------------------


def test_days_overdue_one_day():
    assert days_overdue(make_task(yesterday())) == 1


def test_days_overdue_three_days():
    three_ago = (_vn_today() - timedelta(days=3)).isoformat()
    assert days_overdue(make_task(three_ago)) == 3


def test_days_overdue_today_is_zero():
    assert days_overdue(make_task(today_str())) == 0


def test_days_overdue_future_is_zero():
    assert days_overdue(make_task(tomorrow())) == 0


# ---------------------------------------------------------------------------
# hours_overdue
# ---------------------------------------------------------------------------


def test_hours_overdue_one_day():
    assert hours_overdue(make_task(yesterday())) == 24


def test_hours_overdue_not_overdue_is_zero():
    assert hours_overdue(make_task(tomorrow())) == 0
