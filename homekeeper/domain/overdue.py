from datetime import date, datetime, timedelta, timezone

_VN_TZ = timezone(timedelta(hours=7))


def _vn_today() -> date:
    return datetime.now(_VN_TZ).date()


def is_overdue(task) -> bool:
    """Return True if task's next_due_date is strictly before today (VN timezone)."""
    return date.fromisoformat(task["next_due_date"]) < _vn_today()


def days_overdue(task) -> int:
    """Return number of calendar days overdue (VN timezone). Returns 0 if not overdue."""
    delta = _vn_today() - date.fromisoformat(task["next_due_date"])
    return max(0, delta.days)


def hours_overdue(task) -> int:
    """Return approximate hours overdue (days * 24). Returns 0 if not overdue."""
    return days_overdue(task) * 24
