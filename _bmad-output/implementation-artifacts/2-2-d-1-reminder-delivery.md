---
baseline_commit: NO_VCS
---

# Story 2.2: D-1 Reminder Delivery

Status: done

## Story

As an Admin,
I want to receive a reminder message the day before a task is due,
So that I have time to prepare or arrange for the maintenance.

## Acceptance Criteria

1. **[AC-1] D-1 reminder sent once per task per due-date cycle after 08:00 VN time:**
   Given a Task with `next_due_date = T` and no existing REMINDER_LOG row `type='D-1'` for this due-date cycle,
   when Scheduler runs on day T−1 at or after 08:00 Vietnam time (UTC+7),
   then bot sends message to Admin: `"🔔 Nhắc nhở: <b>[tên Task]</b> đến hạn vào ngày mai ([T as DD/MM/YYYY])."` with `parse_mode="HTML"`,
   and Scheduler inserts one row into REMINDER_LOG: `(task_id, type='D-1', sent_at=UTC_now)`.

2. **[AC-2] Idempotent — no duplicate sends within a due-date cycle:**
   Given a D-1 reminder was already sent for Task X for due date T,
   when Scheduler polls again (same day or after restart),
   then Scheduler does NOT send another D-1 message for Task X / due date T.
   Idempotency is based solely on REMINDER_LOG rows — no in-memory state.

3. **[AC-3] Same reminder forwarded to all Members (text only, no buttons):**
   Given at least one Member exists in the MEMBER table,
   when D-1 reminder is sent,
   then same text message is sent to each Member's `telegram_user_id`; no inline keyboard;
   a failed Member send logs WARNING and continues — does not block the admin send or REMINDER_LOG write.

4. **[AC-4] AD-8 guard applied before REMINDER_LOG write:**
   Given Scheduler decided to send D-1 for Task X,
   when Scheduler calls `_task_unchanged(conn, task_id, due_date)` immediately before inserting into REMINDER_LOG,
   then if `next_due_date` changed (task was edited mid-tick), Scheduler skips the send for this tick.

5. **[AC-5] Scheduler before 08:00 VN time performs no sends:**
   Given current Vietnam time is before 08:00,
   when `_tick()` runs,
   then `_tick()` exits early without checking any tasks for D-1.

## Tasks / Subtasks

- [x] Task 1 — Create `homekeeper/db/reminder_log_repo.py` (AC: 1, 2, 4)
  - [x] `already_sent(conn, task_id: int, reminder_type: str, sent_date: str) -> bool` — `SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND type=? AND date(sent_at)=? LIMIT 1`; `sent_date` is the calendar date the reminder is expected to be sent (YYYY-MM-DD); returns `True` if row found
  - [x] `log_sent(conn, task_id: int, reminder_type: str, sent_at: str) -> int` — `INSERT INTO REMINDER_LOG (task_id, type, sent_at) VALUES (?, ?, ?)`, `conn.commit()`, returns `cursor.lastrowid`
  - [x] Tests in `tests/test_reminder_log_repo.py` (RED→GREEN)

- [x] Task 2 — Create `homekeeper/db/member_repo.py` (AC: 3)
  - [x] `get_all_members(conn) -> list` — `SELECT id, telegram_user_id, name FROM MEMBER ORDER BY id ASC`; returns `cursor.fetchall()` (may be empty list)
  - [x] Tests in `tests/test_member_repo.py` (RED→GREEN)

- [x] Task 3 — Create `homekeeper/scheduler/sender.py` (AC: 1, 3)
  - [x] `send_telegram_message(chat_id: int, text: str) -> None` — reads `TELEGRAM_BOT_TOKEN` from `os.environ`, creates `Bot(token)` inside `async with`, calls `await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")`, wraps in `asyncio.run()`
  - [x] No imports from `homekeeper.bot` (AD-1); no shared Bot instance (fresh per call)
  - [x] Tests in `tests/test_sender.py` — mock `telegram.Bot` to verify correct args

- [x] Task 4 — Update `homekeeper/scheduler/loop.py` to implement D-1 check (AC: 1–5)
  - [x] Add imports at top: `import html`, `import os`, `from datetime import date, datetime, timedelta, timezone`, `from homekeeper.db import reminder_log_repo, member_repo`, `from homekeeper.scheduler import sender`
  - [x] Add `_VN_TZ = timezone(timedelta(hours=7))` module-level constant
  - [x] Update `_tick(conn, _now=None) -> None` signature — `_now` defaults to `datetime.now(_VN_TZ)`; if `_now.hour < 8`, return early; compute `tomorrow = _now.date() + timedelta(days=1)`; iterate tasks, call `_check_d1(conn, task)` for each task where `date.fromisoformat(task["next_due_date"]) == tomorrow`
  - [x] Add `_check_d1(conn, task) -> None` — see exact implementation in Dev Notes
  - [x] Keep all existing comments for Stories 2.3 and 2.5
  - [x] Tests in `tests/test_scheduler_d1.py`

- [x] Task 5 — Verification (AC: 1–5)
  - [x] Full test suite passes, no regressions (97/97)
  - [x] Verify no `homekeeper.bot` imports in `scheduler/` files (AD-1)
  - [x] Verify `already_sent` is checked BEFORE sending (idempotency gate first)
  - [x] Verify `_task_unchanged` is checked BEFORE `log_sent` (AD-8 gate second)
  - [x] Verify `log_sent` is called AFTER successful admin send (don't log if send failed)

## Dev Notes

### Stack & Imports Reference

```python
# PTB version: 22.8 (installed)
# asyncio.run() available (Python 3.12)
# Pattern for sending from non-async thread:
import asyncio
from telegram import Bot

async def _do_send(token, chat_id, text):
    async with Bot(token) as bot:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")

asyncio.run(_do_send(token, chat_id, text))
```

### File Map

```
homekeeper/db/reminder_log_repo.py   ← NEW
homekeeper/db/member_repo.py         ← NEW (get_all_members only; writes come in Epic 4)
homekeeper/scheduler/sender.py       ← NEW
homekeeper/scheduler/loop.py         ← UPDATE (_tick signature + _check_d1 added)
tests/test_reminder_log_repo.py      ← NEW
tests/test_member_repo.py            ← NEW
tests/test_sender.py                 ← NEW
tests/test_scheduler_d1.py           ← NEW
```

### Current State of `loop.py` (Story 2.1 final, after code review)

```python
import logging
import threading
import time

from homekeeper.db.connection import open_db
from homekeeper.db import task_repo

logger = logging.getLogger(__name__)


def _task_unchanged(conn, task_id: int, expected_due_date: str) -> bool:
    row = task_repo.get_task_by_id(conn, task_id)
    if row is None:
        return False
    return row["next_due_date"] == expected_due_date


def _tick(conn) -> None:
    logger.debug("Scheduler tick")
    tasks = task_repo.get_all_tasks(conn)
    # Story 2.2: add D-1 check here; iterate `tasks` and call _task_unchanged(conn, task_id, due_date) before REMINDER_LOG write
    # Story 2.3: add D-0 check here
    # Story 2.5: add overdue check here


def _run_loop() -> None:
    try:
        conn = open_db()
    except Exception as exc:
        logger.error("Scheduler failed to open DB: %s — thread exiting", exc)
        return
    logger.info("Scheduler started — polling every 60 seconds")
    while True:
        try:
            _tick(conn)
        except Exception as exc:
            logger.error("Scheduler tick error: %s", exc)
        time.sleep(60)


def start_scheduler() -> threading.Thread:
    t = threading.Thread(target=_run_loop, name="scheduler", daemon=True)
    t.start()
    return t
```

### Exact Implementation: `reminder_log_repo.py`

```python
import sqlite3


def already_sent(conn: sqlite3.Connection, task_id: int, reminder_type: str, sent_date: str) -> bool:
    """Return True if a reminder of the given type was sent on sent_date for this task.
    sent_date is YYYY-MM-DD of the calendar day the reminder is expected to fire.
    For D-1: pass (due_date - 1 day); for D-0: pass due_date.
    Uses date(sent_at) SQL function to extract calendar date from stored UTC datetime.
    """
    row = conn.execute(
        "SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND type=? AND date(sent_at)=? LIMIT 1",
        (task_id, reminder_type, sent_date),
    ).fetchone()
    return row is not None


def log_sent(conn: sqlite3.Connection, task_id: int, reminder_type: str, sent_at: str) -> int:
    """Insert a REMINDER_LOG row. sent_at is ISO-8601 UTC datetime. Returns new row id."""
    cursor = conn.execute(
        "INSERT INTO REMINDER_LOG (task_id, type, sent_at) VALUES (?, ?, ?)",
        (task_id, reminder_type, sent_at),
    )
    conn.commit()
    return cursor.lastrowid
```

### Exact Implementation: `member_repo.py`

```python
import sqlite3


def get_all_members(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT id, telegram_user_id, name FROM MEMBER ORDER BY id ASC")
    return cursor.fetchall()
```

### Exact Implementation: `sender.py`

```python
import asyncio
import os

from telegram import Bot


def send_telegram_message(chat_id: int, text: str) -> None:
    """Send a Telegram message from the scheduler thread.
    Uses asyncio.run() to create a fresh event loop — safe to call from a sync thread.
    Does NOT import from homekeeper.bot (AD-1). Reads token from env each call.
    Raises on Telegram API error — callers must catch if they want to continue.
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    async def _send():
        async with Bot(token) as bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")

    asyncio.run(_send())
```

### Exact Implementation: Updated `_tick()` and new `_check_d1()`

Add these imports to `loop.py`:
```python
import html
import os
from datetime import date, datetime, timedelta, timezone

from homekeeper.db import member_repo, reminder_log_repo
from homekeeper.scheduler import sender
```

Add module-level constant (after imports, before `logger`):
```python
_VN_TZ = timezone(timedelta(hours=7))
```

Replace `_tick()`:
```python
def _tick(conn, _now=None) -> None:
    """One scheduler tick. _now is injectable for testing (defaults to VN local time)."""
    logger.debug("Scheduler tick")
    tasks = task_repo.get_all_tasks(conn)
    if _now is None:
        _now = datetime.now(_VN_TZ)
    if _now.hour < 8:
        return
    tomorrow = _now.date() + timedelta(days=1)
    for task in tasks:
        try:
            due = date.fromisoformat(task["next_due_date"])
        except (ValueError, TypeError):
            logger.warning("Task %d has invalid next_due_date: %r", task["id"], task["next_due_date"])
            continue
        if due == tomorrow:
            _check_d1(conn, task)
    # Story 2.3: add D-0 check here
    # Story 2.5: add overdue check here
```

Add `_check_d1()` (insert between `_tick` and `_run_loop`):
```python
def _check_d1(conn, task) -> None:
    """Send D-1 reminder if not yet sent for this task's current due-date cycle."""
    task_id = task["id"]
    due_date = task["next_due_date"]  # YYYY-MM-DD

    # D-1 is expected to fire on due_date - 1 day
    reminder_date = (date.fromisoformat(due_date) - timedelta(days=1)).isoformat()

    # Idempotency gate: skip if already sent for this cycle
    if reminder_log_repo.already_sent(conn, task_id, "D-1", reminder_date):
        return

    # AD-8 guard: re-read task to confirm due_date hasn't changed since we decided to send
    if not _task_unchanged(conn, task_id, due_date):
        return

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    text = f"🔔 Nhắc nhở: <b>{html.escape(task['name'])}</b> đến hạn vào ngày mai ({vn_date_display})."

    # Send to admin — if this fails, don't log (retry next tick)
    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, text)
    except Exception as exc:
        logger.error("Failed to send D-1 to admin for task %d: %s", task_id, exc)
        return

    # Log the send — AFTER admin succeeds, BEFORE members (members are best-effort)
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    reminder_log_repo.log_sent(conn, task_id, "D-1", sent_at)
    logger.info("D-1 reminder sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    # Send to members (best-effort — failure does not affect REMINDER_LOG or other members)
    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning(
                "Failed to send D-1 to member %d: %s", member["telegram_user_id"], exc
            )
```

### already_sent Date Logic — Why sent_date = due_date − 1?

```
Task due_date = "2026-07-01"
D-1 reminder expected on 2026-06-30 at 08:00+ VN

already_sent(conn, task_id, "D-1", "2026-06-30")
→ SELECT 1 FROM REMINDER_LOG WHERE task_id=X AND type='D-1' AND date(sent_at)='2026-06-30'
→ False on first check (08:01 VN June 30) → proceeds to send
→ True on subsequent ticks (08:02, 08:03...) → skips ✓

When task is marked Done on 2026-07-01, next_due_date advances to 2026-08-01.
D-1 for 2026-08-01 fires on 2026-07-31:
already_sent(conn, task_id, "D-1", "2026-07-31") → False (no row for July 31) → sends ✓
```

### Test Strategy

**`tests/test_reminder_log_repo.py` (new, use in-memory conn fixture):**
```python
# Fixture: same conn pattern as other tests — :memory: + schema.sql + row_factory
# Also need a task to FK reference in REMINDER_LOG:
#   task_id = create_task(conn, "T", 30, "2026-07-01")

def test_already_sent_false_when_no_rows(conn): ...
def test_already_sent_true_when_row_exists(conn): ...      # insert row, check same date → True
def test_already_sent_false_when_date_differs(conn): ...   # insert row, check different date → False
def test_already_sent_false_when_type_differs(conn): ...   # insert 'D-0', check 'D-1' → False
def test_log_sent_creates_row(conn): ...                   # log_sent(), query REMINDER_LOG → 1 row
def test_log_sent_returns_row_id(conn): ...                # returns integer > 0
```

**`tests/test_member_repo.py` (new):**
```python
def test_get_all_members_empty(conn): ...        # no members → []
def test_get_all_members_returns_all(conn): ...  # insert 2 members → list of 2
```

**`tests/test_sender.py` (new, mock telegram.Bot):**
```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

def test_send_telegram_message_calls_bot(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    mock_bot = AsyncMock()
    mock_bot.__aenter__ = AsyncMock(return_value=mock_bot)
    mock_bot.__aexit__ = AsyncMock(return_value=False)
    with patch("homekeeper.scheduler.sender.Bot", return_value=mock_bot):
        from homekeeper.scheduler.sender import send_telegram_message
        send_telegram_message(12345, "test message")
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=12345, text="test message", parse_mode="HTML"
    )
```

**`tests/test_scheduler_d1.py` (new):**
```python
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from homekeeper.scheduler.loop import _check_d1, _tick

# Use same conn fixture from conftest or copy it

def test_tick_skips_before_8am(conn):
    # _now = 07:59 VN → _tick returns without checking any tasks
    from homekeeper.db.task_repo import create_task
    create_task(conn, "T", 30, tomorrow_vn_str())  # task due tomorrow
    vn_now = make_vn_time(hour=7, minute=59)
    # patch sender to fail if called
    with patch("homekeeper.scheduler.loop.sender") as mock_sender:
        _tick(conn, _now=vn_now)
    mock_sender.send_telegram_message.assert_not_called()

def test_tick_sends_after_8am(conn, monkeypatch):
    # task due tomorrow, _now = 08:01 VN → D-1 should be sent
    ...

def test_check_d1_sends_when_not_yet_sent(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")
    task_id = create_task(conn, "Task", 30, tomorrow_str())
    task = task_repo.get_task_by_id(conn, task_id)
    with patch("homekeeper.scheduler.loop.sender.send_telegram_message") as mock_send:
        _check_d1(conn, task)
    mock_send.assert_called_once()  # admin send
    # verify REMINDER_LOG has one row
    row = conn.execute("SELECT type FROM REMINDER_LOG WHERE task_id=?", (task_id,)).fetchone()
    assert row["type"] == "D-1"

def test_check_d1_skips_when_already_sent(conn, monkeypatch):
    # insert REMINDER_LOG row for yesterday (= today - 1, which is reminder_date for tomorrow's task)
    # → already_sent returns True → no send
    ...

def test_check_d1_skips_when_task_changed(conn, monkeypatch):
    # after already_sent returns False, task's due_date changes before _task_unchanged check
    # → _task_unchanged returns False → no send, no log
    ...

def test_check_d1_no_log_on_send_failure(conn, monkeypatch):
    # send_telegram_message raises → no REMINDER_LOG row inserted
    ...

def test_check_d1_sends_to_members(conn, monkeypatch):
    # insert 2 members, verify send_telegram_message called 3 times (admin + 2 members)
    ...

def test_check_d1_continues_on_member_failure(conn, monkeypatch):
    # first member send raises, second member should still be attempted
    ...
```

**Helper utilities for tests:**
```python
from datetime import date, timedelta, datetime, timezone

def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()

def make_vn_time(hour: int, minute: int = 0) -> datetime:
    vn_tz = timezone(timedelta(hours=7))
    # Use a fixed date to avoid midnight edge cases in tests
    return datetime(2026, 6, 29, hour, minute, 0, tzinfo=vn_tz)
```

### Critical Anti-Patterns — DO NOT DO THESE

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `from homekeeper.bot import ...` in scheduler/ | Only `homekeeper.db.*`, `homekeeper.scheduler.*`, stdlib |
| `asyncio.get_event_loop().run_until_complete(...)` | `asyncio.run(...)` — creates fresh loop per call |
| Create `Bot` once at module level | Create fresh `async with Bot(token) as bot:` per send call |
| `already_sent(conn, task_id, "D-1")` without date | Must pass `sent_date` — otherwise blocks future cycles |
| Call `log_sent` before `send_telegram_message` | Log AFTER successful admin send |
| Call `_task_unchanged` before `already_sent` | Check `already_sent` FIRST (cheap read), then `_task_unchanged` |
| `date.today()` for tomorrow calculation | `_now.date() + timedelta(days=1)` — use VN time, not UTC |
| Write `TASK.next_due_date` in scheduler | Scheduler is read-only on TASK (AD-8) |
| Share `conn` with PTB thread | Scheduler has own `conn` from `open_db()` in `_run_loop()` |
| Send members without try/except | Wrap per-member send — one failure must not block others |

### Architecture Constraints (Story 2.2)

| Rule | How Story 2.2 satisfies it |
|------|---------------------------|
| AD-1 Downward-only imports | `scheduler/` imports only `db/` and stdlib; no `bot/` imports |
| AD-2 No shared in-memory state | scheduler reads `ADMIN_USER_ID` from env; no PTB Application reference |
| AD-3 Domain layer pure Python | No business logic in `domain/` for this story (date math done inline) |
| AD-4 No external HTTP (HITL) | `Bot.send_message()` is Telegram messaging, not external integration |
| AD-5 One connection per thread | Scheduler's `conn` is from `open_db()` inside `_run_loop()` — never shared |
| AD-8 Scheduler read-only on TASK | `_check_d1` only reads TASK (via `_task_unchanged`); writes only REMINDER_LOG |

### Story 2.1 Learnings (Carry Forward)

- `_task_unchanged(conn, task_id, due_date)` is already implemented in `loop.py` — reuse it
- `tasks = task_repo.get_all_tasks(conn)` in `_tick()` already returns list of `sqlite3.Row`
- `open_db()` wraps in try/except in `_run_loop()` — do NOT call it again in 2.2
- `asyncio.run()` creates a new event loop — fine for scheduler (not PTB loop)
- Daemon thread pattern: scheduler dies with process, no cleanup needed

### REMINDER_LOG Schema Reference

```sql
CREATE TABLE IF NOT EXISTS REMINDER_LOG (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES TASK(id),
    type         TEXT    NOT NULL,  -- 'D-1' | 'D-0' | 'overdue' | 'catchup'
    sent_at      TEXT    NOT NULL,  -- ISO-8601 UTC datetime YYYY-MM-DDTHH:MM:SS
    confirmed_at TEXT               -- NULL until Admin taps Done or Skip (Story 2.3)
);
```

### Source References

- [Source: planning-artifacts/epics.md — Story 2.2 Acceptance Criteria]
- [Source: planning-artifacts/architecture/ARCHITECTURE-SPINE.md — AD-1, AD-2, AD-4, AD-5, AD-8]
- [Source: implementation-artifacts/2-1-scheduler-infrastructure.md — _task_unchanged, _tick pattern, loop.py current state]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_

### Completion Notes List

_

### File List

- `homekeeper/db/reminder_log_repo.py` — NEW (Task 1)
- `homekeeper/db/member_repo.py` — NEW (Task 2)
- `homekeeper/scheduler/sender.py` — NEW (Task 3)
- `homekeeper/scheduler/loop.py` — UPDATED: added `_check_d1`, updated `_tick` signature with `_now`, imports, `_VN_TZ` (Task 4)
- `tests/test_reminder_log_repo.py` — NEW (Task 1)
- `tests/test_member_repo.py` — NEW (Task 2)
- `tests/test_sender.py` — NEW (Task 3)
- `tests/test_scheduler_d1.py` — NEW (Task 4): 12 tests covering time-gate, idempotency, AD-8 guard, member forwarding, error handling

### Change Log

- Task 3: Fixed `test_sender.py` — removed `importlib.reload` inside patch context which was overriding the mock by re-importing real `telegram.Bot`. Tests now use `patch.object` pattern without reload.
- Task 4: `_tick` now accepts `_now=None` injectable time; added `_check_d1` with full D-1 logic (idempotency gate → AD-8 guard → admin send → log → member sends best-effort).
- Task 5: 97/97 tests pass; no `homekeeper.bot` imports in `scheduler/`; operation order verified (already_sent → _task_unchanged → send → log_sent).

### Review Findings

- [x] [Review][Patch] P1: `_tick` fetches all tasks before the 08:00 hour gate — `get_all_tasks` called before the early-exit guard, doing a needless DB scan on every pre-8am tick [loop.py:75]
- [x] [Review][Patch] P2: `sent_at` stored without timezone marker — `strftime("%Y-%m-%dT%H:%M:%S")` omits `Z`/`+00:00`, making the field ambiguous for future readers [loop.py:57]
- [x] [Review][Defer] D1: AC-4 guard positioned before send, not immediately before `log_sent` [loop.py:42] — deferred; current placement prevents sending stale text; moving after send would create a send-without-log gap on task mutation
- [x] [Review][Defer] D2: `asyncio.run()` raises if called from within a running event loop [sender.py:21] — deferred; safe in current sync daemon thread; revisit only if scheduler moves to async
- [x] [Review][Defer] D3: No `UNIQUE(task_id, type, date(sent_at))` constraint on REMINDER_LOG [schema.sql] — deferred; single-threaded scheduler today; add constraint when multi-instance support added
- [x] [Review][Defer] D4: Members skipped on retry when log is written before member sends complete [loop.py:58-69] — deferred; spec-intentional per AC-3 (REMINDER_LOG write must not be blocked by member sends)
- [x] [Review][Defer] D5: Bot creates a new HTTPS session per recipient [sender.py] — deferred; acceptable latency at household scale (1–5 members)
- [x] [Review][Defer] D6: Task name TOCTOU — stale name in message if renamed between `get_all_tasks` and `_task_unchanged` [loop.py:46] — deferred; spec AC-4 only guards `next_due_date`; name staleness is acceptable
- [x] [Review][Defer] D7: No scheduler shutdown event [loop.py] — deferred; pre-existing from Story 2.1; daemon thread sufficient for current use
- [x] [Review][Defer] D8: `_task_unchanged` returns `False` on deleted task with no diagnostic log [loop.py:17-20] — deferred; deleted tasks disappear from future ticks; low impact
