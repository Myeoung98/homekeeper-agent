---
status: ready-for-dev
baseline_commit: NO_VCS
---

# Story 2.5: Overdue Hourly Re-notification & Catch-up on Restart

Status: done

## Story

As an Admin,
I want to be reminded every hour when a task is overdue and receive missed reminders after a restart,
So that nothing falls through the cracks even if I miss the initial reminder or the bot was offline.

## Acceptance Criteria

**AC-1 — Overdue hourly re-notification:**
**Given** Task có `next_due_date < hôm nay` và chưa có `confirmed_at` trong REMINDER_LOG cho cycle hiện tại
**When** Scheduler chạy và đã qua ít nhất 1 giờ kể từ lần Overdue Reminder gần nhất (dựa trên REMINDER_LOG)
**Then** Bot gửi Reminder cho Admin: "⚠️ Quá hạn: **[tên Task]** đã trễ [N] ngày. Bạn đã xử lý chưa?" kèm inline keyboard nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
**And** Scheduler ghi row vào REMINDER_LOG: `type='overdue', sent_at=now`
**And** Member nhận tin nhắn text thuần (không có inline keyboard): "⚠️ Quá hạn: **[tên Task]** đã trễ [N] ngày."

**AC-2 — Stop overdue once confirmed:**
**Given** Admin tap "✅ Hoàn thành" hoặc "⏭ Bỏ qua" trên overdue Reminder
**When** `reminder_callbacks.py` ghi `confirmed_at` và gọi `advance_next_due_date` (AD-8)
**Then** Scheduler dừng gửi Overdue Reminder cho Task đó (vì `next_due_date` đã được advance sang cycle mới, `is_overdue` trả về False)

**AC-3 — Catch-up on restart:**
**Given** Bot vừa khởi động lại
**When** `scheduler/catchup.py` chạy ngay khi startup (trước khi scheduler thread bắt đầu)
**Then** `catchup.py` query REMINDER_LOG để tìm Task có `next_due_date ≤ hôm nay` và chưa có Reminder row nào cho `due_date` đó (kiểm tra bằng `any_sent_on_date`)
**And** Với mỗi Task bị bỏ lỡ, bot gửi ngay một catch-up Reminder cho Admin với label "⚡ Gửi bù (bot vừa khởi động lại)" kèm inline keyboard
**And** Ghi row vào REMINDER_LOG với `type='catchup'` để đánh dấu đã gửi

**AC-4 — Catch-up idempotency (D-0 blocked after catchup):**
**Given** Task có `next_due_date = hôm nay` và catch-up đã gửi (REMINDER_LOG có `type='catchup'` trên `due_date`)
**When** Scheduler poll tiếp theo chạy `_check_d0`
**Then** `_check_d0` không gửi lại D-0 (idempotency check dùng `any_sent_on_date` bắt được `type='catchup'` row)

## Tasks / Subtasks

- [x] Task 1: Thêm DB repo helpers vào `reminder_log_repo.py` (AC: 1, 3, 4)
  - [x] 1.1 Thêm `get_latest_sent_at(conn, task_id, reminder_type) → str | None` — trả về `sent_at` mới nhất cho task+type combo, dùng để check 1-hour gate của overdue
  - [x] 1.2 Thêm `any_sent_on_date(conn, task_id, sent_date) → bool` — trả về True nếu bất kỳ row nào trong REMINDER_LOG có `task_id=?` AND `date(sent_at)=?`, dùng cho catch-up skip check
  - [x] 1.3 Viết unit tests cho 2 hàm mới (happy path, empty result)

- [x] Task 2: Tạo `homekeeper/domain/overdue.py` (AC: 1)
  - [x] 2.1 Implement `is_overdue(task) → bool`: trả về `date.fromisoformat(task["next_due_date"]) < date.today()` (AD-3: pure Python only, no telegram/sqlite3)
  - [x] 2.2 Implement `days_overdue(task) → int`: trả về `(date.today() - date.fromisoformat(task["next_due_date"])).days`
  - [x] 2.3 Implement `hours_overdue(task) → int`: trả về số giờ kể từ 08:00 sáng ngày đến hạn (có thể dùng trong future display)
  - [x] 2.4 Viết pure-Python unit tests (không cần DB hay SQLite)

- [x] Task 3: Thêm `_check_overdue` vào `loop.py` và sửa `_check_d0` idempotency (AC: 1, 2, 4)
  - [x] 3.1 Viết tests FAIL (RED): overdue send triggers, 1-hour gate blocks, task not overdue skips, admin send failure no log, member receives text no keyboard
  - [x] 3.2 Implement `_check_overdue(conn, task)` — xem spec chi tiết bên dưới
  - [x] 3.3 Sửa `_check_d0` idempotency: thay `already_sent(conn, task_id, "D-0", reminder_date)` bằng `any_sent_on_date(conn, task_id, reminder_date)` (để block D-0 khi catch-up đã gửi)
  - [x] 3.4 Wire `_check_overdue` vào `_tick()` thay thế comment `# Story 2.5: add overdue check here`
  - [x] 3.5 Chạy tests GREEN, bao gồm toàn bộ test suite không bị regression

- [x] Task 4: Tạo `homekeeper/scheduler/catchup.py` (AC: 3, 4)
  - [x] 4.1 Viết tests FAIL (RED): no missed tasks, task due today no log → sends + writes row, task overdue no log → sends, task already has any row → skips, send failure graceful
  - [x] 4.2 Implement `run_catchup(conn)` — xem spec chi tiết bên dưới
  - [x] 4.3 Chạy tests GREEN

- [x] Task 5: Wire catchup vào `main.py` (AC: 3)
  - [x] 5.1 Import `run_catchup` từ `homekeeper.scheduler.catchup`
  - [x] 5.2 Gọi `run_catchup(app_db)` sau `open_db()`, trước `start_scheduler()`, trong `try/except` để không crash startup nếu catchup fail

- [x] Task 6: Chạy full test suite, xác nhận không có regression

### Review Findings (2026-07-01)

- [x] [Review][Patch] P1: Member overdue message includes "Bạn đã xử lý chưa?" — spec requires truncated form for members (AC-1) [loop.py:138 / catchup.py:43-51]
- [x] [Review][Patch] P2: `overdue.py` uses server-local `date.today()` — on UTC servers, 7-hour window where `is_overdue` mis-fires vs `_tick`'s VN-aware today [overdue.py:6,11]
- [x] [Review][Patch] P3: `_send_catchup` recomputes `today` independently from `run_catchup`; midnight boundary can produce "đã trễ 0 ngày" or wrong branch [catchup.py:38]
- [x] [Review][Patch] P4: `_check_overdue` 1-hour gate only checks `type='overdue'`; recent `type='catchup'` send not considered — overdue fires 60s after catch-up on restart [loop.py:128]
- [x] [Review][Defer] D1: `confirmed_at` guard from AC-1 Given not implemented — deferred, dev notes document advance mechanism is sufficient; AC-2 path already validated
- [x] [Review][Defer] D2: `confirm_reminder` silently updates multiple rows if same type+date sent twice — deferred, pre-existing, not introduced by Story 2.5
- [x] [Review][Defer] D3: `_run_loop` no DB reconnect on dead connection — deferred, pre-existing pattern shared with earlier stories
- [x] [Review][Defer] D4: Read-check-send-log race in `_check_overdue` — deferred, pre-existing pattern consistent with `_check_d0`/`_check_d1`
- [x] [Review][Defer] D5: `hours_overdue` is dead code / spec inconsistency (task 2.3 text vs code snippet) — deferred, harmless, may be used by future story
- [x] [Review][Defer] D6: `any_sent_on_date` UTC date near midnight — deferred, root cause addressed by P2 (timezone fix); deep SQLite tzdata fix is future work
- [x] [Review][Defer] D7: `run_catchup` fires catch-up on every restart for multi-day-overdue tasks (spec-compliant: checks due_date, not recent sends) — deferred, noisy but spec-defined behavior

## Dev Notes

### Architecture Constraints

- **AD-3 (CRITICAL):** `domain/overdue.py` — KHÔNG được import `telegram`, `sqlite3`, hay bất kỳ third-party library. Chỉ Python stdlib (`datetime`, `date`). AD-3 ensures domain is pure Python.
- **AD-6 (CRITICAL):** `scheduler/catchup.py` là module startup scan. Chạy từ main thread TRƯỚC khi scheduler thread start. Nhận `conn` parameter từ caller — KHÔNG tự gọi `open_db()`.
- **AD-2:** `catchup.py` không import gì từ `bot/`. Chỉ import từ `db/`, `scheduler/sender`.
- **AD-8:** `scheduler/catchup.py` là read-only trên TASK. `run_catchup` KHÔNG gọi `advance_next_due_date`. Chỉ đọc task, gửi message, ghi REMINDER_LOG.
- **AD-5:** `run_catchup(conn)` nhận `conn` từ caller (main thread's `app_db`). An toàn vì PTB chưa start khi catchup chạy. Scheduler thread sau đó mở connection riêng của nó.
- **AD-1:** `loop.py` và `catchup.py` đều import từ `homekeeper.db.*` và `homekeeper.domain.*`. KHÔNG import từ `homekeeper.bot.*`.

### Module Structure

```
homekeeper/
  domain/
    overdue.py             # NEW: is_overdue(task), days_overdue(task), hours_overdue(task)
  scheduler/
    catchup.py             # NEW: run_catchup(conn)
    loop.py                # MODIFIED: _check_overdue + _tick update + _check_d0 fix
  db/
    reminder_log_repo.py   # MODIFIED: get_latest_sent_at + any_sent_on_date
main.py                    # MODIFIED: call run_catchup(app_db)
```

### domain/overdue.py — Full Spec

```python
from datetime import date

def is_overdue(task) -> bool:
    """Return True if task's next_due_date is before today."""
    return date.fromisoformat(task["next_due_date"]) < date.today()

def days_overdue(task) -> int:
    """Return number of days overdue. Returns 0 if not overdue."""
    delta = date.today() - date.fromisoformat(task["next_due_date"])
    return max(0, delta.days)

def hours_overdue(task) -> int:
    """Return approximate hours overdue (days * 24). Used for display only."""
    return days_overdue(task) * 24
```

Tests live in `tests/test_domain_overdue.py` — pure sync, no DB needed, pass a dict `{"next_due_date": "2026-06-28"}`.

### reminder_log_repo.py — New Helpers

```python
def get_latest_sent_at(
    conn: sqlite3.Connection,
    task_id: int,
    reminder_type: str,
) -> str | None:
    """Return the most recent sent_at for this task/type, or None if never sent."""
    row = conn.execute(
        "SELECT sent_at FROM REMINDER_LOG WHERE task_id=? AND type=? "
        "ORDER BY sent_at DESC LIMIT 1",
        (task_id, reminder_type),
    ).fetchone()
    return row["sent_at"] if row else None


def any_sent_on_date(
    conn: sqlite3.Connection,
    task_id: int,
    sent_date: str,
) -> bool:
    """Return True if any reminder (any type) was sent for this task on sent_date.

    sent_date is YYYY-MM-DD. Uses SQLite date() to extract calendar date from sent_at.
    Used by: catchup.py (skip check) and _check_d0 (block re-send after catchup).
    """
    row = conn.execute(
        "SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND date(sent_at)=? LIMIT 1",
        (task_id, sent_date),
    ).fetchone()
    return row is not None
```

### _check_overdue — Full Spec (loop.py)

```python
def _check_overdue(conn, task) -> None:
    """Send hourly overdue reminder if task is overdue and 1+ hour since last overdue send."""
    from homekeeper.domain.overdue import is_overdue, days_overdue

    task_id = task["id"]
    due_date = task["next_due_date"]

    if not is_overdue(task):
        return

    # 1-hour gate: check when last overdue was sent
    latest_sent_at = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
    if latest_sent_at is not None:
        sent_dt = datetime.fromisoformat(latest_sent_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - sent_dt < timedelta(hours=1):
            return  # too soon

    # AD-8 guard: re-read task to confirm due_date unchanged
    if not _task_unchanged(conn, task_id, due_date):
        return

    n = days_overdue(task)
    text = f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> đã trễ {n} ngày. Bạn đã xử lý chưa?"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done:{task_id}:{due_date}"),
            InlineKeyboardButton("⏭ Bỏ qua lần này", callback_data=f"skip:{task_id}:{due_date}"),
        ]
    ])

    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Failed to send overdue to admin for task %d: %s", task_id, exc)
        return

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "overdue", sent_at)
    logger.info("Overdue reminder sent: task_id=%d name=%r due=%s days_overdue=%d",
                task_id, task["name"], due_date, n)

    # Members receive plain text, no keyboard (FR-8 / Epic 4 AC)
    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning("Failed to send overdue to member %d: %s",
                           member["telegram_user_id"], exc)
```

**_tick update** — replace `# Story 2.5: add overdue check here` with:
```python
        if due < today:
            _check_overdue(conn, task)
```

**_check_d0 idempotency fix** — change existing line:
```python
# OLD:
if reminder_log_repo.already_sent(conn, task_id, "D-0", reminder_date):
# NEW:
if reminder_log_repo.any_sent_on_date(conn, task_id, reminder_date):
```

This change is safe: existing tests pass because they insert `type='D-0'` rows (which `any_sent_on_date` still finds). New behavior: catch-up rows (`type='catchup'`) on the same date also block D-0 resend.

### scheduler/catchup.py — Full Spec

```python
import html
import logging
import os
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from homekeeper.db import reminder_log_repo, task_repo, member_repo
from homekeeper.scheduler import sender

logger = logging.getLogger(__name__)


def run_catchup(conn) -> None:
    """Send catch-up reminders for all missed tasks at startup.

    A "missed" task has next_due_date <= today with no REMINDER_LOG row on that date.
    Runs in the main thread before the scheduler daemon starts (AD-6).
    Logs type='catchup' — _check_d0 uses any_sent_on_date so it won't re-send.
    """
    today = date.today().isoformat()
    tasks = task_repo.get_all_tasks(conn)

    for task in tasks:
        due_date = task["next_due_date"]
        if due_date > today:
            continue  # not yet due

        # Skip if any reminder already sent for this due_date cycle
        if reminder_log_repo.any_sent_on_date(conn, task["id"], due_date):
            continue

        _send_catchup(conn, task, due_date)


def _send_catchup(conn, task, due_date: str) -> None:
    """Send one catch-up reminder and log it."""
    task_id = task["id"]
    today = date.today().isoformat()

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    if due_date < today:
        days_late = (date.today() - date.fromisoformat(due_date)).days
        text = (
            f"⚡ Gửi bù (bot vừa khởi động lại): "
            f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> "
            f"đến hạn {vn_date_display} — đã trễ {days_late} ngày."
        )
    else:  # due_date == today
        text = (
            f"⚡ Gửi bù (bot vừa khởi động lại): "
            f"📅 Đến hạn hôm nay: <b>{html.escape(task['name'])}</b> ({vn_date_display})."
        )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Hoàn thành", callback_data=f"done:{task_id}:{due_date}"),
            InlineKeyboardButton("⏭ Bỏ qua lần này", callback_data=f"skip:{task_id}:{due_date}"),
        ]
    ])

    admin_id = int(os.environ["ADMIN_USER_ID"])
    try:
        sender.send_telegram_message(admin_id, text, reply_markup=keyboard)
    except Exception as exc:
        logger.error("Catch-up send failed for task %d: %s — skipping log", task_id, exc)
        return

    from datetime import datetime, timezone
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "catchup", sent_at)
    logger.info("Catch-up sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning("Catch-up member send failed %d: %s", member["telegram_user_id"], exc)
```

### main.py Update

Add after `app_db = open_db()` and before `start_scheduler()`:

```python
from homekeeper.scheduler.catchup import run_catchup

# In main(), after open_db() success:
try:
    run_catchup(app_db)
except Exception as exc:
    logger.warning("Catch-up scan failed: %s — continuing", exc)
```

### Callback Data — Overdue Buttons

Overdue reminders use the SAME callback_data format as D-0:
- `done:{task_id}:{due_date}` and `skip:{task_id}:{due_date}`

The existing `handle_reminder_callback` in `reminder_callbacks.py` handles these automatically:
1. Stale check: `task["next_due_date"] != due_date_str` — if task was already advanced, stale.
2. `confirm_reminder(conn, task_id, "D-0", due_date_str, confirmed_at)` — rowcount may be 0 if only overdue rows exist; warning logged, advance still runs.
3. `advance_next_due_date(conn, task_id, new_due_date)` — advances to future date → AC-2 naturally satisfied.

**No changes needed to `reminder_callbacks.py`.**

### AC-2 Mechanism (Important)

The overdue reminders stop naturally — no extra check needed:

1. Admin taps done/skip on overdue message (or original D-0 message)
2. `advance_next_due_date` sets `TASK.next_due_date = old_due + cycle_days`
3. Next `_tick`: `is_overdue(task)` → `new_due_date < today` → False (for normal cycle_days ≥ 1)
4. `_check_overdue` returns early → no more overdue sends

Edge case: if `cycle_days = 1` and the task has been overdue for many days, `new_due_date` could still be in the past. In that case:
- The new cycle (`new_due_date`) has no overdue REMINDER_LOG rows yet
- `get_latest_sent_at("overdue")` returns rows from the OLD cycle, which are recent
- 1-hour gate would block for ~1 hour, then resume for the new cycle

This is acceptable behavior for a personal household bot.

### 1-Hour Gate Implementation Detail

```python
latest_sent_at = reminder_log_repo.get_latest_sent_at(conn, task_id, "overdue")
if latest_sent_at is not None:
    # Parse UTC datetime — sent_at uses hardcoded "Z" suffix
    sent_dt = datetime.fromisoformat(latest_sent_at.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - sent_dt < timedelta(hours=1):
        return
```

Note: `datetime.fromisoformat` works for `"2026-07-01T08:00:00+00:00"` (Python 3.11+). For Python 3.12+ (project requirement), this is guaranteed.

### Scheduler Tick Flow After Story 2.5

```
_tick(conn, _now):
  if _now.hour < 8: return

  for task in tasks:
    due = date.fromisoformat(task["next_due_date"])
    if due == tomorrow:  _check_d1(conn, task)   # send D-1
    if due == today:     _check_d0(conn, task)   # send D-0 (uses any_sent_on_date now)
    if due < today:      _check_overdue(conn, task)  # NEW: send overdue hourly
```

### Test Architecture

**tests/test_domain_overdue.py** — pure sync, no DB:
```python
def make_task(due_date: str) -> dict:
    return {"next_due_date": due_date}

def test_is_overdue_past_date():  # yesterday → True
def test_is_overdue_today():      # today → False
def test_is_overdue_future():     # tomorrow → False
def test_days_overdue_2_days():   # 2 days ago → 2
def test_days_overdue_not_overdue():  # tomorrow → 0
```

**tests/test_scheduler_overdue.py** — scheduler overdue logic:
```python
# Uses same conn fixture and make_vn_time pattern as test_scheduler_d0.py
# Key tests:
def test_check_overdue_sends_when_overdue():           # sends and logs
def test_check_overdue_skips_if_not_overdue():         # today → skip
def test_check_overdue_respects_1_hour_gate():         # sent 30min ago → skip
def test_check_overdue_fires_after_1_hour():           # sent 61min ago → sends
def test_check_overdue_no_log_on_admin_failure():      # send fails → no log
def test_check_overdue_members_get_no_keyboard():      # member call has no reply_markup
def test_tick_sends_overdue_for_past_due_task():       # integration via _tick
def test_tick_d0_blocked_by_catchup_row():             # catchup row blocks D-0 resend
```

**tests/test_scheduler_catchup.py** — catchup logic:
```python
def test_catchup_skips_future_tasks():
def test_catchup_sends_for_due_today_no_log():
def test_catchup_sends_for_overdue_no_log():
def test_catchup_skips_when_any_row_exists():           # D-0 or catchup already there
def test_catchup_admin_receives_keyboard():
def test_catchup_members_receive_message():
def test_catchup_handles_admin_send_failure_gracefully():
def test_catchup_message_includes_label():              # "Gửi bù" in text
def test_catchup_logs_catchup_type():                   # type='catchup' in REMINDER_LOG
def test_main_catchup_call_uses_app_db():               # integration: main.py wires it correctly
```

### Existing Code Must Be Preserved

When modifying `loop.py`:
1. `_check_d1` — no changes needed
2. `_check_d0` — ONLY change the idempotency check line (`already_sent` → `any_sent_on_date`). All other logic preserved.
3. `_tick` — ONLY add `if due < today: _check_overdue(conn, task)`. The `if due == tomorrow` and `if due == today` branches remain.
4. `_run_loop` and `start_scheduler` — no changes.

When modifying `main.py`:
1. All existing handler registrations preserved.
2. `run_catchup(app_db)` added between `open_db()` and `start_scheduler()`.
3. `start_scheduler()` call preserved.

### Previous Story Learnings (from Stories 2.2–2.4)

- `already_sent` pattern: `SELECT 1 FROM REMINDER_LOG WHERE task_id=? AND type=? AND date(sent_at)=? LIMIT 1` — `date()` extracts calendar date from UTC datetime string.
- `_task_unchanged` guard: always call before writing REMINDER_LOG (AD-8 guard pattern).
- `send_telegram_message` raises on Telegram error — callers catch and return early (no log on failure).
- `sent_at` format: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` — hardcoded Z (consistent across codebase).
- Members use same text, no `reply_markup` argument (defaults to None in `sender.send_telegram_message`).
- Test fixture `conn` pattern: `:memory:` SQLite, `c.row_factory = sqlite3.Row`, executescript `schema.sql`.
- `monkeypatch.setenv("ADMIN_USER_ID", "999")` in all scheduler/bot tests.
- `patch("homekeeper.scheduler.loop.sender.send_telegram_message")` to mock sends.
- `make_vn_time(hour, minute)` helper in D-0/D-1 tests for `_tick` injection.

### Deferred Items from Previous Stories Affecting This Story

From `deferred-work.md` (2-3):
- **Scheduler down on D-0 day silently drops the reminder:** Story 2.5's `catchup.py` MUST handle this. ✅ AC-3 covers this: `run_catchup` sends on startup if no row exists.
- **Stale buttons after catch-up:** catch-up sends use same `done:{task_id}:{due_date}` format. If admin was sent a catch-up for `due_date` and bot restarts again, the old catch-up button has stale `due_date`. `reminder_callbacks.py`'s stale check (`task["next_due_date"] != due_date_str`) handles this correctly.

### References

- [Source: epics.md — Story 2.5 ACs + Epic 4 AC-4.2 member receives overdue text no keyboard]
- [Source: architecture/ARCHITECTURE-SPINE.md — AD-6 catch-up rule, AD-8 single writer, structural seed]
- [Source: homekeeper/scheduler/loop.py:119-139] — `_tick()` placeholder comment, `_check_d0`/`_check_d1` patterns
- [Source: homekeeper/db/reminder_log_repo.py] — existing `already_sent`, `log_sent` patterns
- [Source: homekeeper/db/schema.sql:22-28] — REMINDER_LOG with `type` comment listing 'overdue' and 'catchup'
- [Source: homekeeper/scheduler/sender.py] — `send_telegram_message(chat_id, text, reply_markup=None)`
- [Source: main.py] — `open_db()` → `application` build → `start_scheduler()` sequence
- [Source: deferred-work.md — "Scheduler down on D-0 day"] — Story 2.5 cross-story obligation

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Task 3: `test_tick_sends_overdue_for_past_due_task` failed because VN fixed date and task due date were both 2026-06-29, making `due == today` instead of `due < today`. Fixed by using "2026-06-28" as task due date (day before VN fixed date).

### Completion Notes List

- All 4 ACs implemented: AC-1 (hourly overdue via `_check_overdue`), AC-2 (natural stop via `is_overdue` returning False after advance), AC-3 (catch-up on restart via `run_catchup`), AC-4 (D-0 idempotency via `any_sent_on_date`).
- `_check_d0` idempotency changed from `already_sent("D-0", ...)` to `any_sent_on_date(...)` so catch-up rows also block D-0 re-send.
- 170 tests passing, 0 regressions.

### File List

- homekeeper/domain/overdue.py (NEW)
- homekeeper/scheduler/catchup.py (NEW)
- homekeeper/db/reminder_log_repo.py (MODIFIED — added get_latest_sent_at, any_sent_on_date)
- homekeeper/scheduler/loop.py (MODIFIED — _check_overdue + _tick + _check_d0 fix)
- main.py (MODIFIED — run_catchup import + call)
- tests/test_domain_overdue.py (NEW — 10 tests)
- tests/test_scheduler_overdue.py (NEW — 14 tests)
- tests/test_scheduler_catchup.py (NEW — 11 tests)
- tests/test_db_helpers_2_5.py (NEW — 8 tests)

### Change Log

- homekeeper/db/reminder_log_repo.py: added `get_latest_sent_at(conn, task_id, type)` and `any_sent_on_date(conn, task_id, date)`
- homekeeper/domain/overdue.py: new module — `is_overdue`, `days_overdue`, `hours_overdue`
- homekeeper/scheduler/loop.py: added `_check_overdue`; wired into `_tick`; fixed `_check_d0` to use `any_sent_on_date`
- homekeeper/scheduler/catchup.py: new module — `run_catchup(conn)` and `_send_catchup`
- main.py: import `run_catchup`; call `run_catchup(app_db)` in `try/except` before `start_scheduler()`
