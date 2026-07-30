---
status: ready-for-dev
baseline_commit: NO_VCS
---

# Story 2.4: Task Completion & Auto-Reschedule

Status: done

## Story

As an Admin,
I want to confirm a task as done (or skip it) with one tap on the D-0 reminder button,
so that the bot automatically schedules the next occurrence without me having to calculate anything.

## Acceptance Criteria

**AC-1 — Done tap advances task:**
**Given** Admin nhận D-0 Reminder với nút "✅ Hoàn thành"
**When** Admin tap nút "✅ Hoàn thành"
**Then** `bot/reminder_callbacks.py` cập nhật REMINDER_LOG row hiện tại với `confirmed_at=now` (AD-8)
**And** `bot/reminder_callbacks.py` ghi `TASK.next_due_date = due_date_cũ + cycle_days` (single writer — AD-8)
**And** Bot reply bằng tin nhắn: "✅ Đã ghi nhận: **[tên Task]** hoàn thành. Hạn tiếp theo: [ngày mới DD/MM/YYYY]."

**AC-2 — Skip tap advances task (same reschedule, different reply):**
**Given** Admin nhận D-0 Reminder với nút "⏭ Bỏ qua lần này"
**When** Admin tap nút "⏭ Bỏ qua lần này"
**Then** REMINDER_LOG row được đánh dấu `confirmed_at=now`
**And** `TASK.next_due_date` được tính lại = `due_date_cũ + cycle_days`
**And** Bot reply: "⏭ Đã bỏ qua. Hạn tiếp theo: [ngày mới DD/MM/YYYY]."

**AC-3 — Stale button rejected (no DB update):**
**Given** Reminder message đã cũ — task đã được xác nhận trước đó và `next_due_date` đã được cập nhật
**When** Admin tap vào nút cũ trên một message cũ
**Then** Bot reply bằng popup alert: "Reminder này đã hết hiệu lực. Xem /list để biết trạng thái hiện tại."
**And** Không có thay đổi nào trong DB

**AC-4 — Non-admin callback silently ignored:**
**Given** User không phải Admin tap vào nút (nếu họ thấy được message)
**When** Bot nhận callback query từ non-admin user
**Then** Bot answer callback (clear spinner) nhưng không thực hiện bất kỳ DB operation nào

**AC-5 — Handler registered:**
**Given** `main.py` khởi động bot
**When** Application được build
**Then** `CallbackQueryHandler` cho pattern `^(done|skip):\d+:\d{4}-\d{2}-\d{2}$` được đăng ký

## Tasks / Subtasks

- [x] Task 1: Thêm DB helper functions (AC: 1, 2)
  - [x] 1.1 Thêm `confirm_reminder(conn, task_id, reminder_type, sent_date, confirmed_at)` vào `reminder_log_repo.py` — UPDATE REMINDER_LOG SET confirmed_at WHERE task_id+type+date(sent_at)
  - [x] 1.2 Thêm `advance_next_due_date(conn, task_id, new_due_date)` vào `task_repo.py` — UPDATE TASK SET next_due_date WHERE id
  - [x] 1.3 Viết unit tests cho 2 hàm mới (happy path, row not found no-op)

- [x] Task 2: Tạo `homekeeper/bot/reminder_callbacks.py` với callback handler (AC: 1, 2, 3, 4)
  - [x] 2.1 Viết tests FAIL trước (RED): parse valid callback_data, stale detection, done path DB calls, skip path DB calls, non-admin rejection
  - [x] 2.2 Implement handler: parse callback_data → stale check → admin check → DB operations → reply
  - [x] 2.3 Chạy tests để xác nhận GREEN

- [x] Task 3: Đăng ký CallbackQueryHandler trong `main.py` (AC: 5)
  - [x] 3.1 Import handler từ `bot/reminder_callbacks.py`
  - [x] 3.2 Thêm `application.add_handler(CallbackQueryHandler(..., pattern=...))` vào `main()`

- [x] Task 4: Chạy full test suite, xác nhận không có regression

## Dev Notes

### Architecture Constraints

- **AD-8 (CRITICAL):** `bot/reminder_callbacks.py` là WRITER DUY NHẤT được phép ghi `TASK.next_due_date`. Scheduler (`loop.py`) là read-only trên TASK. Không bao giờ ghi next_due_date từ scheduler.
- **AD-1:** `bot/` không được import từ `scheduler/`. Mọi import chỉ từ `homekeeper.db.*`.
- **AD-2:** `bot/reminder_callbacks.py` dùng connection `context.bot_data["db"]` (PTB thread's connection, opened in `main.py`). Không tạo connection mới.
- **AD-5:** Mỗi thread giữ một DB connection riêng — callback handler dùng `context.bot_data["db"]`, không tạo `open_db()` mới.

### Callback Data Format

Callback data được encode bởi `loop.py:_check_d0()`:
```python
callback_data=f"done:{task_id}:{due_date}"   # "done:3:2026-07-01"
callback_data=f"skip:{task_id}:{due_date}"   # "skip:3:2026-07-01"
```

Parse pattern: `action, task_id_str, due_date_str = data.split(":", 2)`

Handler pattern cho `CallbackQueryHandler`: `r'^(done|skip):\d+:\d{4}-\d{2}-\d{2}$'`

### Stale Button Detection

Mechanism: so sánh `due_date` từ callback_data với `TASK.next_due_date` hiện tại trong DB.

```python
task = task_repo.get_task_by_id(conn, int(task_id_str))
if task is None or task["next_due_date"] != due_date_str:
    # Stale: task deleted or already advanced
    await query.answer("Reminder này đã hết hiệu lực. Xem /list để biết trạng thái hiện tại.", show_alert=True)
    return
```

Điều này bảo đảm idempotency: lần tap đầu advance task (next_due_date thay đổi), lần tap thứ hai bị stale check catch.

### DB Operations Sequence

Cho cả `done` và `skip` (cùng DB effect, khác reply text):

```python
conn = context.bot_data["db"]
task = task_repo.get_task_by_id(conn, task_id)

# Stale check (see above)

new_due_date = (date.fromisoformat(due_date_str) + timedelta(days=task["cycle_days"])).isoformat()
confirmed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

reminder_log_repo.confirm_reminder(conn, task_id, "D-0", due_date_str, confirmed_at)
task_repo.advance_next_due_date(conn, task_id, new_due_date)
```

**Note:** `confirm_reminder` và `advance_next_due_date` mỗi hàm commit riêng (consistent với pattern hiện tại). Nếu `advance_next_due_date` fail sau khi `confirm_reminder` succeed: REMINDER_LOG đã có `confirmed_at` nên scheduler không gửi D-0 lại; task giữ nguyên next_due_date cũ nên Story 2.5 sẽ gửi overdue reminder. Acceptable risk cho personal bot.

### PTB v22 Callback Handler Pattern

```python
from telegram import Update
from telegram.ext import ContextTypes

async def handle_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # acknowledge immediately — MUST call to clear spinner
    ...
```

Quan trọng: `await query.answer()` phải được gọi **ngay đầu handler**, trước mọi xử lý. Nếu không, Telegram hiển thị loading spinner mãi mãi ở phía Admin.

Để hiển thị popup alert (AC-3 stale):
```python
await query.answer("message text", show_alert=True)
return  # no further action
```

Để reply tin nhắn vào chat (AC-1, AC-2 confirmation):
```python
await query.answer()  # clear spinner
await query.message.reply_text("✅ Đã ghi nhận: ...")
```

### Admin Check in Callback

Không dùng `@admin_only` decorator (nó dùng `reply_text` trên message — không phù hợp với callback). Thực hiện inline:

```python
admin_id = int(os.environ["ADMIN_USER_ID"])
if update.effective_user is None or update.effective_user.id != admin_id:
    await query.answer()  # clear spinner silently
    return
```

### Files to Create

- **NEW:** `homekeeper/bot/reminder_callbacks.py`
- **NEW:** `tests/test_reminder_callbacks.py`

### Files to Modify

- **UPDATE:** `homekeeper/db/reminder_log_repo.py` — thêm `confirm_reminder()`
- **UPDATE:** `homekeeper/db/task_repo.py` — thêm `advance_next_due_date()`
- **UPDATE:** `main.py` — import và đăng ký `CallbackQueryHandler`

### New DB Functions Spec

**`reminder_log_repo.confirm_reminder`:**
```python
def confirm_reminder(
    conn: sqlite3.Connection,
    task_id: int,
    reminder_type: str,
    sent_date: str,     # YYYY-MM-DD — same as "reminder_date" used in already_sent
    confirmed_at: str,  # ISO-8601 UTC datetime
) -> int:
    """Mark the matching REMINDER_LOG row as confirmed.
    sent_date is the calendar date used in already_sent (for D-0: == due_date).
    Returns rowcount (0 if no matching row found — caller can log/ignore).
    """
    cursor = conn.execute(
        "UPDATE REMINDER_LOG SET confirmed_at=? "
        "WHERE task_id=? AND type=? AND date(sent_at)=?",
        (confirmed_at, task_id, reminder_type, sent_date),
    )
    conn.commit()
    return cursor.rowcount
```

**`task_repo.advance_next_due_date`:**
```python
def advance_next_due_date(conn: sqlite3.Connection, task_id: int, new_due_date: str) -> None:
    """Update only next_due_date for the given task. Single-writer constraint: only bot/reminder_callbacks.py calls this (AD-8)."""
    conn.execute("UPDATE TASK SET next_due_date=? WHERE id=?", (new_due_date, task_id))
    conn.commit()
```

### Testing Strategy for Async PTB Handlers

Async PTB handlers cần `AsyncMock` từ `unittest.mock`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, CallbackQuery, Message, User, Chat

@pytest.mark.asyncio
async def test_handle_done(conn, monkeypatch):
    monkeypatch.setenv("ADMIN_USER_ID", "999")

    # Build mock update
    query = MagicMock(spec=CallbackQuery)
    query.data = f"done:{task_id}:{due_date}"
    query.answer = AsyncMock()
    query.message = MagicMock(spec=Message)
    query.message.reply_text = AsyncMock()

    user = MagicMock(spec=User)
    user.id = 999  # admin

    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    context = MagicMock()
    context.bot_data = {"db": conn}

    from homekeeper.bot.reminder_callbacks import handle_reminder_callback
    await handle_reminder_callback(update, context)

    query.answer.assert_called_once()
    query.message.reply_text.assert_called_once()
    # assert DB was updated
```

Cần `pytest-asyncio` (xác nhận đã được dùng ở project — nếu chưa có, add vào requirements.txt / pyproject.toml).

Kiểm tra: `python3 -c "import pytest_asyncio; print(pytest_asyncio.__version__)"` trước khi viết tests.

### Deferred Items from Story 2.3 Affecting This Story

Từ `deferred-work.md`, section 2-3:
- **Stale keyboard buttons (cross-story contract):** Story 2.4 phải validate `due_date` trong callback_data vs TASK.next_due_date. ✅ Được xử lý trong AC-3 và stale detection logic trên.

### Registration in main.py

```python
from telegram.ext import CallbackQueryHandler
from homekeeper.bot.reminder_callbacks import handle_reminder_callback

# Trong main(), sau khi build application:
application.add_handler(
    CallbackQueryHandler(
        handle_reminder_callback,
        pattern=r'^(done|skip):\d+:\d{4}-\d{2}-\d{2}$',
    )
)
```

Pattern này match đúng format `"done:3:2026-07-01"` và `"skip:3:2026-07-01"` và reject các callback_data khác (Story 3.x sẽ dùng pattern riêng).

### Previous Story Learnings (from Story 2.3)

- `asyncio.run()` trong scheduler thread là safe (không có running event loop trong daemon thread).
- `reply_markup=None` là default — explicit khi cần override.
- Test fixture `conn` dùng `:memory:` SQLite với `schema.sql` executescript.
- `monkeypatch.setenv("ADMIN_USER_ID", "999")` pattern cho tất cả bot/scheduler tests.
- `date.today().isoformat()` cho due_date trong unit tests; fixed date cho `_tick` integration tests.

### Project Structure Notes

- `homekeeper/bot/reminder_callbacks.py` — new module trong `bot/` package. Không cần update `homekeeper/bot/__init__.py` (handler registered trực tiếp trong `main.py`).
- `tests/test_reminder_callbacks.py` — parallel với `tests/test_scheduler_d0.py`.
- `pytest-asyncio` mode: kiểm tra `pyproject.toml` / `pytest.ini` xem có cần `asyncio_mode = "auto"` không.

### References

- [Source: epics.md — Story 2.4 ACs]
- [Source: homekeeper/scheduler/loop.py:91-95] — callback_data format được encode ở đây
- [Source: homekeeper/db/schema.sql:22-28] — REMINDER_LOG schema với confirmed_at column
- [Source: homekeeper/db/reminder_log_repo.py] — existing pattern cho repo functions
- [Source: homekeeper/db/task_repo.py] — existing pattern cho repo functions
- [Source: main.py:57-63] — ApplicationBuilder + handler registration pattern
- [Source: homekeeper/bot/__init__.py] — admin_only decorator (không dùng trong callback — xem Admin Check section)
- [Source: deferred-work.md — "Stale keyboard buttons"] — Story 2.4 cross-story contract từ 2.3 review

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Stale path initially used `query.answer(text, show_alert=True)` after the bare `query.answer()` — Telegram API only allows one `answerCallbackQuery` per callback. Fixed: stale path uses `query.message.reply_text()` instead; tests updated to match.

### Completion Notes List

- AC-1 done: `done` tap sets REMINDER_LOG.confirmed_at + advances TASK.next_due_date + replies "✅ Đã ghi nhận: **[tên]** hoàn thành. Hạn tiếp theo: DD/MM/YYYY."
- AC-2 done: `skip` tap identical DB effect, reply text "⏭ Đã bỏ qua. Hạn tiếp theo: DD/MM/YYYY."
- AC-3 done: stale check via `task.next_due_date != callback_due_date`; deleted task also caught (task is None). Reply via `reply_text` (not show_alert) to avoid double-answering the callback query.
- AC-4 done: non-admin cleared (bare `query.answer()`), no DB operations, no reply_text.
- AC-5 done: `CallbackQueryHandler` registered in `main.py` with pattern `^(done|skip):\d+:\d{4}-\d{2}-\d{2}$`.
- 126/126 tests pass, zero regressions.

### File List

- homekeeper/bot/reminder_callbacks.py (NEW)
- homekeeper/db/reminder_log_repo.py (MODIFIED — added confirm_reminder)
- homekeeper/db/task_repo.py (MODIFIED — added advance_next_due_date)
- main.py (MODIFIED — CallbackQueryHandler registration, CALLBACK_PATTERN import)
- tests/test_reminder_callbacks.py (NEW — 10 async tests)
- tests/test_db_helpers_2_4.py (NEW — 6 unit tests)

### Review Findings

- [x] [Review][Patch] P1: `query.message is None` guard missing — crash on deleted message or channel send [`reminder_callbacks.py:47,77`] — fixed: guard added after `query.answer()`; test `test_none_message_returns_silently` added
- [x] [Review][Patch] P2: `_CALLBACK_PATTERN` duplicated as string literal in `main.py` instead of imported from module — drift risk [`main.py:66`, `reminder_callbacks.py:13`] — fixed: renamed to `CALLBACK_PATTERN`, exported, imported in `main.py`
- [x] [Review][Patch] P3: Stale-button reply prepends `⚠️` emoji not present in AC-3 spec text [`reminder_callbacks.py:47-49`] — fixed: emoji removed
- [x] [Review][Defer] D1: No atomicity between `confirm_reminder` and `advance_next_due_date` — partial state on crash [`reminder_callbacks.py:58-64`] — deferred, acknowledged in Dev Notes as acceptable risk
- [x] [Review][Defer] D2: TOCTOU double-advance on two simultaneous taps [`reminder_callbacks.py:46-64`] — deferred, PTB sequential update processing mitigates in practice; pre-existing architectural limit
- [x] [Review][Defer] D3: `confirmed_at` uses `strftime("%Y-%m-%dT%H:%M:%SZ")` hardcoded `Z` suffix [`reminder_callbacks.py:54`] — deferred, consistent pre-existing pattern across codebase
- [x] [Review][Defer] D4: `ADMIN_USER_ID=""` logs "not a valid integer" instead of "not configured" — inconsistency with `admin_only` decorator [`reminder_callbacks.py:27-32`] — deferred, diagnostic quality only, no functional impact
- [x] [Review][Defer] D5: `confirm_reminder rowcount=0` scenario untested — advance still runs without audit row [`reminder_callbacks.py:58-63`] — deferred, intentional design acknowledged in Dev Notes
- [x] [Review][Defer] D6: `task_handlers.py update_task()` also writes `TASK.next_due_date`, pre-existing AD-8 gap — deferred, pre-existing, out-of-scope for this story
- [x] [Review][Defer] D7: `query.data` can be `None` — `split()` AttributeError if handler invoked without PTB pattern routing [`reminder_callbacks.py:38-39`] — deferred, PTB pattern in `main.py` prevents `None` reaching handler in production

### Change Log

- 2026-07-01: Story 2.4 implemented — callback handler for done/skip buttons, DB helpers, main.py registration. 15 new tests, 126 total passing.
- 2026-07-01: Code review patches applied — P1: query.message None guard + test; P2: _CALLBACK_PATTERN renamed/exported/imported; P3: stale reply emoji removed. 127 total passing.
