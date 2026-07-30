# Story 2.1: Scheduler Infrastructure

Status: done

## Story

As an Admin,
I want the bot to continuously check for upcoming tasks in the background,
So that reminders fire automatically without me doing anything after initial setup.

## Acceptance Criteria

1. **[AC-1] Scheduler thread starts parallel with PTB event loop:** Given Admin chạy `python main.py`, when bot khởi động, then scheduler thread được khởi động song song với PTB event loop; hai thread không chia sẻ biến in-memory nào — giao tiếp chỉ qua SQLite (AD-2).

2. **[AC-2] 60-second poll cycle with DEBUG logging:** Given scheduler thread đang chạy, when mỗi 60 giây, then scheduler query tất cả Task từ DB, kiểm tra xem Task nào đến hạn cần gửi Reminder, và ghi log tick ở level DEBUG.

3. **[AC-3] Re-read Task before REMINDER_LOG write (AD-8 guard):** Given scheduler đọc một Task để gửi Reminder, when scheduler chuẩn bị ghi vào REMINDER_LOG, then scheduler re-reads row Task từ DB để xác nhận `next_due_date` chưa thay đổi kể từ khi nó quyết định gửi; nếu đã thay đổi, bỏ qua tick này cho Task đó. (Infrastructure helper implemented in 2.1; actual use in Stories 2.2+.)

4. **[AC-4] No SQLITE_BUSY errors:** Given bot đang chạy và SQLite được mở, when cả PTB thread và scheduler thread đều ghi DB đồng thời, then không xảy ra lỗi `SQLITE_BUSY`; mỗi thread giữ connection riêng, WAL mode đã bật (AD-5).

## Tasks / Subtasks

- [x] Task 1 — Create `homekeeper/scheduler/loop.py` (AC: 1, 2, 3, 4)
  - [x] Add `_task_unchanged(conn, task_id: int, expected_due_date: str) -> bool` — calls `task_repo.get_task_by_id(conn, task_id)`; returns `False` if row is `None`; returns `row["next_due_date"] == expected_due_date` (AD-8 guard for Stories 2.2+)
  - [x] Add `_tick(conn) -> None` — calls `logger.debug("Scheduler tick")` then `task_repo.get_all_tasks(conn)` (scheduler is read-only on TASK per AD-8); no other action in Story 2.1
  - [x] Add `_run_loop() -> None` — calls `open_db()` to get own connection (AD-5), logs INFO "Scheduler started — polling every 60 seconds", then infinite `while True` loop: `try: _tick(conn)` / `except Exception: logger.error(...)` / `time.sleep(60)`
  - [x] Add `start_scheduler() -> threading.Thread` — creates `threading.Thread(target=_run_loop, name="scheduler", daemon=True)`, calls `.start()`, returns thread
  - [x] Imports in loop.py: `logging`, `threading`, `time` (stdlib) + `homekeeper.db.connection.open_db` + `homekeeper.db.task_repo` — NO imports from `homekeeper.bot` (AD-1)

- [x] Task 2 — Update `main.py` to start scheduler (AC: 1)
  - [x] Add import: `from homekeeper.scheduler.loop import start_scheduler`
  - [x] Replace `# TODO Story 2.1: start scheduler thread here` with `start_scheduler()`
  - [x] Call `start_scheduler()` BEFORE `application.run_polling()` (scheduler must be up before PTB blocks)
  - [x] Keep ALL existing main.py code unchanged

- [x] Task 3 — Tests in `tests/test_scheduler_loop.py` (AC: 1, 2, 3, 4)
  - [x] Fixture `conn`: `:memory:` SQLite, `row_factory = sqlite3.Row`, schema.sql applied
  - [x] `test_tick_does_not_raise_empty_db` — `_tick(conn)` on empty DB does not raise
  - [x] `test_tick_does_not_raise_with_tasks` — add task via `create_task()`, `_tick(conn)` does not raise
  - [x] `test_tick_logs_debug` — `caplog.at_level(DEBUG, logger="homekeeper.scheduler.loop")`, assert "Scheduler tick" in caplog.text
  - [x] `test_task_unchanged_true_when_date_matches` — insert task with due "2099-07-01", assert `_task_unchanged(conn, task_id, "2099-07-01")` is True
  - [x] `test_task_unchanged_false_when_date_differs` — insert task with "2099-07-01", assert `_task_unchanged(conn, task_id, "2099-08-01")` is False
  - [x] `test_task_unchanged_false_when_task_missing` — assert `_task_unchanged(conn, 9999, "2099-07-01")` is False
  - [x] `test_start_scheduler_returns_daemon_thread` — `patch("homekeeper.scheduler.loop._run_loop")`, call `start_scheduler()`, assert `t.daemon is True`
  - [x] `test_start_scheduler_thread_name` — same patch, assert `t.name == "scheduler"`
  - [x] `test_start_scheduler_calls_run_loop` — use `threading.Event` to verify `_run_loop` was called

- [x] Task 4 — Verification (AC: 1–4)
  - [x] `python3 -c "import ast; ast.parse(open('homekeeper/scheduler/loop.py').read())"` — syntax clean
  - [x] `python3 -c "import ast; ast.parse(open('main.py').read())"` — syntax clean
  - [x] Verify loop.py imports nothing from `homekeeper.bot` (AD-1)
  - [x] Verify thread is `daemon=True` in `start_scheduler()`
  - [x] Verify `open_db()` is called inside `_run_loop` (not passed from main) (AD-5)
  - [x] Run full test suite — all tests pass, no regressions

## Dev Notes

### Stack (carry-forward from Epic 1)

- Python ≥ 3.12, PTB ≥ 21.0 async, SQLite bundled (WAL mode via `open_db()`)
- Test framework: pytest + pytest-asyncio; `sqlite3.connect(":memory:")` for DB fixtures

### Threading Model

```
main() thread (PTB event loop)       scheduler thread
  └── application.run_polling()        └── _run_loop()
       [blocks until Ctrl-C]               conn = open_db()  ← own connection (AD-5)
                                           while True:
                                               _tick(conn)
                                               time.sleep(60)
```

- `daemon=True` — scheduler thread dies automatically when main process exits (no cleanup needed for personal bot)
- `time.sleep(60)` — simple; no threading.Event needed in 2.1
- Two threads NEVER share Python objects for coordination — they both READ SQLite; `bot/` WRITES `next_due_date` (AD-2, AD-8)

### Files Being Modified — Read Before Touching

```
homekeeper/scheduler/loop.py  ← NEW (create)
homekeeper/scheduler/__init__.py  ← EXISTS (empty, do not touch)
main.py                       ← UPDATE (import + call start_scheduler)
tests/test_scheduler_loop.py  ← NEW (create)
```

### Current State of main.py (Story 1.4 final)

```python
# Relevant section:
from homekeeper.bot.task_handlers import (
    build_add_conversation,
    build_delete_conversation,
    build_edit_conversation,
    list_handler,
)
from homekeeper.db.connection import open_db
# ... (TELEGRAM_BOT_TOKEN validation, open_db() call, ApplicationBuilder, handlers)

    # TODO Story 2.1: start scheduler thread here   ← REPLACE THIS LINE

    logger.info("HomeKeeper Agent started")
    application.run_polling()
```

Change needed in main.py:
```python
# ADD to imports (near other homekeeper imports):
from homekeeper.scheduler.loop import start_scheduler

# REPLACE the TODO comment with:
start_scheduler()
```

### open_db() — Reuse, Do Not Reinvent

`homekeeper/db/connection.py` already implements `open_db()`:
```python
def open_db() -> sqlite3.Connection:
    db_path = os.environ["DB_PATH"]
    conn = sqlite3.connect(db_path)  # check_same_thread=True enforces AD-5
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    # runs schema.sql (idempotent CREATE TABLE IF NOT EXISTS)
    return conn
```

- `check_same_thread=True` (SQLite default) means the connection object itself rejects cross-thread use at runtime — correctly enforces AD-5
- WAL mode enables concurrent readers + writers without SQLITE_BUSY (AC-4)
- Call `open_db()` INSIDE `_run_loop()`, NOT in `main()` and NOT as a parameter

### Exact Implementation for loop.py

```python
import logging
import threading
import time

from homekeeper.db.connection import open_db
from homekeeper.db import task_repo

logger = logging.getLogger(__name__)


def _task_unchanged(conn, task_id: int, expected_due_date: str) -> bool:
    """Re-read Task to confirm next_due_date hasn't changed (AD-8 guard).
    Returns False if task was deleted or date changed — caller must skip send.
    Used by Stories 2.2+ before each REMINDER_LOG write.
    """
    row = task_repo.get_task_by_id(conn, task_id)
    if row is None:
        return False
    return row["next_due_date"] == expected_due_date


def _tick(conn) -> None:
    """One scheduler tick: query all tasks, check for due reminders."""
    logger.debug("Scheduler tick")
    task_repo.get_all_tasks(conn)
    # Story 2.2: add D-1 check here; call _task_unchanged(conn, task_id, due_date) before REMINDER_LOG write
    # Story 2.3: add D-0 check here
    # Story 2.5: add overdue check here


def _run_loop() -> None:
    """Scheduler thread body: opens own DB connection, polls every 60 seconds."""
    conn = open_db()
    logger.info("Scheduler started — polling every 60 seconds")
    while True:
        try:
            _tick(conn)
        except Exception as exc:
            logger.error("Scheduler tick error: %s", exc)
        time.sleep(60)


def start_scheduler() -> threading.Thread:
    """Spawn scheduler as a daemon thread. Returns the started thread."""
    t = threading.Thread(target=_run_loop, name="scheduler", daemon=True)
    t.start()
    return t
```

### Critical Anti-Patterns — DO NOT DO THESE

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| `conn = open_db()` in `main()`, passed to scheduler | `conn = open_db()` inside `_run_loop()` |
| `from homekeeper.bot import something` in loop.py | Only import `homekeeper.db.*` and stdlib |
| `context.application.bot_data["db"]` in scheduler | `open_db()` — PTB's conn is PTB-thread only |
| `async def _run_loop()` / `await` inside thread | Sync thread only — no async in scheduler loop |
| Writing to `TASK.next_due_date` from scheduler | Scheduler is read-only on TASK (AD-8) |
| `threading.Thread(daemon=False)` | Always `daemon=True` — kills with process |
| `import asyncio` in loop.py | Not needed in 2.1; asyncio pattern comes in 2.2 |

### Test Strategy for Infinite Loop

`_run_loop` has an infinite `while True`. To test `start_scheduler()` without hanging, mock `_run_loop`:

```python
# Pattern 1: mock returns immediately
def test_start_scheduler_returns_daemon_thread():
    with patch("homekeeper.scheduler.loop._run_loop"):
        t = start_scheduler()
    assert t.daemon is True
    assert t.name == "scheduler"

# Pattern 2: verify _run_loop was actually called
def test_start_scheduler_calls_run_loop():
    called = threading.Event()
    def fake_run_loop():
        called.set()
    with patch("homekeeper.scheduler.loop._run_loop", side_effect=fake_run_loop):
        start_scheduler()
    assert called.wait(timeout=2.0)
```

For `_tick()` tests, pass the in-memory `conn` fixture directly — no mocking needed:
```python
def test_tick_does_not_raise_empty_db(conn):
    _tick(conn)  # if it raises, test fails

def test_tick_logs_debug(conn, caplog):
    import logging
    with caplog.at_level(logging.DEBUG, logger="homekeeper.scheduler.loop"):
        _tick(conn)
    assert "Scheduler tick" in caplog.text
```

For `_task_unchanged()` tests, use real in-memory DB with `create_task()`:
```python
def test_task_unchanged_true_when_date_matches(conn):
    task_id = create_task(conn, "Task", 30, "2099-07-01")
    assert _task_unchanged(conn, task_id, "2099-07-01") is True
```

### AC-3 Scope Clarification

AC-3 says "before writing REMINDER_LOG, re-read Task to confirm `next_due_date` hasn't changed." In Story 2.1, there are no REMINDER_LOG writes (that's Stories 2.2+). Story 2.1 satisfies AC-3 by:
1. Implementing `_task_unchanged()` helper with correct logic
2. Documenting in `_tick()` comments that Stories 2.2+ must call it before each send
3. Testing the helper in `test_scheduler_loop.py`

The actual call site (`_tick()` calling `_task_unchanged()`) is Story 2.2's task.

### task_repo Functions Available (Reuse)

```python
# Already implemented in homekeeper/db/task_repo.py — do NOT recreate
task_repo.get_all_tasks(conn)       # → list of sqlite3.Row
task_repo.get_task_by_id(conn, id)  # → sqlite3.Row | None  (used by _task_unchanged)
```

The scheduler does NOT need `create_task`, `update_task`, or `delete_task` — those are bot-layer operations. Scheduler is read-only on TASK (AD-8).

### Story 1.4 Learnings (Relevant to 2.1)

- **`try/except Exception` wrapping** — applied to `_tick()` in the loop, so one bad tick doesn't crash the thread
- **Separate `try/except` for each failure point** — `_tick()` is one call, so one block suffices in `_run_loop`
- **Logging pattern** — `logger = logging.getLogger(__name__)` at module level; INFO for startup, ERROR for exceptions, DEBUG for ticks

### Architecture Constraints Reference

| Rule | Story 2.1 compliance |
|------|---------------------|
| AD-1 Downward-only imports | loop.py imports only `homekeeper.db.*` and stdlib — no `bot/` imports ✓ |
| AD-2 No shared in-memory state between bot and scheduler | Scheduler opens own DB conn; no shared variables, queues, or events ✓ |
| AD-5 One connection per thread | `open_db()` called inside `_run_loop`, not shared from main ✓ |
| AD-8 Scheduler read-only on TASK | `_tick` only calls `get_all_tasks`; `_task_unchanged` calls `get_task_by_id` (both read-only) ✓ |

### File List for This Story

```
homekeeper/scheduler/loop.py       ← NEW (scheduler thread: _tick, _run_loop, start_scheduler, _task_unchanged)
main.py                            ← UPDATE (import start_scheduler, call before run_polling)
tests/test_scheduler_loop.py       ← NEW (9 tests for _tick, _task_unchanged, start_scheduler)
```

### References

- [Source: planning-artifacts/epics.md — Story 2.1 Acceptance Criteria]
- [Source: planning-artifacts/architecture/ARCHITECTURE-SPINE.md — AD-1, AD-2, AD-5, AD-8]
- [Source: implementation-artifacts/1-4-edit-and-delete-task.md — Story 1.4 patterns, logging conventions]
- [Source: homekeeper/db/connection.py — open_db() implementation to reuse]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- No new dependencies required; threading and time are stdlib

### Completion Notes List

- Created `homekeeper/scheduler/loop.py` with `_task_unchanged`, `_tick`, `_run_loop`, `start_scheduler`
- `start_scheduler()` spawns a daemon thread named "scheduler" — dies with process automatically
- `_run_loop()` calls `open_db()` inside the thread body (AD-5: never share PTB-thread connection)
- `_tick()` calls `task_repo.get_all_tasks()` read-only (AD-8: scheduler never writes TASK)
- `_task_unchanged()` implements AD-8 re-read guard for Stories 2.2+ REMINDER_LOG writes
- Updated `main.py`: added `start_scheduler()` call before `application.run_polling()`, removed TODO comment
- No bot/ imports in scheduler/ (AD-1 compliant): only `homekeeper.db.*` and stdlib
- 9 new tests + 61 existing = 70 tests, 0 failures

### File List

- homekeeper/scheduler/loop.py (new — _task_unchanged, _tick, _run_loop, start_scheduler)
- main.py (updated — import start_scheduler, call before run_polling)
- tests/test_scheduler_loop.py (new — 9 tests for _tick, _task_unchanged, start_scheduler)

### Review Findings

- [x] [Review][Patch] `open_db()` call in `_run_loop` is outside try/except — DB init failure produces no log output and silently kills the scheduler daemon thread [homekeeper/scheduler/loop.py:_run_loop] — RESOLVED: wrapped in try/except, logs error and returns; added test_run_loop_exits_on_db_open_failure
- [x] [Review][Patch] `get_all_tasks()` return value discarded in `_tick` — bare expression `task_repo.get_all_tasks(conn)` means Story 2.2 authors must add the assignment; current scaffold is a latent trap [homekeeper/scheduler/loop.py:_tick:26] — RESOLVED: changed to `tasks = task_repo.get_all_tasks(conn)`
- [x] [Review][Defer] `start_scheduler()` has no idempotency guard — double-call spawns duplicate scheduler threads [homekeeper/scheduler/loop.py:start_scheduler] — deferred, called exactly once in main(); daemon threads die with process; low real-world risk on single-admin personal bot
- [x] [Review][Defer] Broken DB connection mid-loop swallowed silently — persistent tick errors would suppress reminders forever with no escalation [homekeeper/scheduler/loop.py:_run_loop] — deferred, acceptable degraded-mode behavior for personal bot
- [x] [Review][Defer] `time.sleep(60)` blocks SIGTERM/SIGINT delivery up to 60 seconds — `threading.Event().wait(60)` would allow clean interrupt [homekeeper/scheduler/loop.py:_run_loop] — deferred, minor UX for personal bot; no functional impact
- [x] [Review][Defer] Scheduler DB connection is never explicitly closed on thread death — connection handle leaked to OS on process exit [homekeeper/scheduler/loop.py:_run_loop] — deferred, OS handles cleanup on process exit; WAL mode handles no explicit close safely
- [x] [Review][Defer] No test verifying `_run_loop` calls `open_db()` independently (AD-5 coverage gap) [tests/test_scheduler_loop.py] — deferred, hard to unit-test an infinite loop; all `start_scheduler` tests mock `_run_loop`; behavior verified by design review
- [x] [Review][Defer] WAL mode not exercised in test fixture — `:memory:` DB skips `open_db()` and its `PRAGMA journal_mode=WAL` [tests/test_scheduler_loop.py:conn fixture] — deferred, WAL mode validated at connection.py level; requires tempfile-based DB to test at scheduler level
- [x] [Review][Defer] `test_start_scheduler_calls_run_loop` assertion has no message — `assert called.wait(timeout=2.0)` fails cryptically [tests/test_scheduler_loop.py:test_start_scheduler_calls_run_loop] — deferred, minor test-quality nit
