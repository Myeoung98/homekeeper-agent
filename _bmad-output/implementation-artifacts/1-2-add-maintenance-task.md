# Story 1.2: Add Maintenance Task

---
baseline_commit: NO_VCS
---

Status: done

## Story

As a Admin,
I want to add a recurring maintenance task through a step-by-step conversation,
So that the bot knows what to remind me about and when.

## Acceptance Criteria

1. **[AC-1] /add entry:** Given Admin gửi `/add`, when bot nhận lệnh, then bot hỏi: "Tên công việc là gì? (ví dụ: Thay lõi lọc nước)"

2. **[AC-2] Name capture:** Given Admin nhập tên công việc (không rỗng), when bot nhận tên, then bot hỏi: "Chu kỳ lặp lại? (ví dụ: 30 ngày, 90 ngày, 180 ngày)"

3. **[AC-3] Cycle capture:** Given Admin nhập chu kỳ hợp lệ (số nguyên dương, có thể kèm đơn vị "ngày"), when bot nhận cycle, then bot hỏi: "Ngày đến hạn tiếp theo? (định dạng DD/MM/YYYY)"

4. **[AC-4] Date capture & save:** Given Admin nhập ngày hợp lệ theo định dạng DD/MM/YYYY, when bot nhận ngày, then bot lưu Task vào SQLite và xác nhận: `✅ Đã thêm: <b>[tên]</b> — đến hạn [ngày], nhắc trước 1 ngày vào [ngày−1].`

5. **[AC-5] Validation — empty name:** Given Admin bỏ trống tên (whitespace-only), when bot validate, then bot báo lỗi cụ thể và yêu cầu nhập lại — không lưu Task, không tiến sang bước tiếp theo.

6. **[AC-6] Validation — invalid cycle:** Given Admin nhập cycle = 0 hoặc không chứa số nguyên dương, when bot validate, then bot báo lỗi cụ thể và yêu cầu nhập lại — không lưu Task.

7. **[AC-7] /cancel anywhere:** Given Admin gửi `/cancel` trong bất kỳ bước nào, when bot nhận `/cancel`, then bot hủy flow và trả về: "Đã hủy. Task không được lưu." — conversation kết thúc.

## Tasks / Subtasks

- [x] Task 1 — DB layer: task_repo (AC: 4)
  - [x] Create `homekeeper/db/task_repo.py` with `create_task(conn, name, cycle_days, next_due_date) -> int`
  - [x] `created_at` stored as `datetime.utcnow().isoformat(timespec="seconds")` (UTC, ISO-8601)
  - [x] `next_due_date` stored as `date.isoformat()` → "YYYY-MM-DD" string
  - [x] Commit after INSERT, return `cursor.lastrowid`

- [x] Task 2 — Bot handler: ConversationHandler for /add (AC: 1, 2, 3, 4, 5, 6, 7)
  - [x] Create `homekeeper/bot/task_handlers.py`
  - [x] Define states: `ASK_NAME, ASK_CYCLE, ASK_DATE = range(3)`
  - [x] `add_start(update, context) -> int`: `@admin_only` decorated, reply with AC-1 prompt, return `ASK_NAME`
  - [x] `receive_name(update, context) -> int`: strip whitespace; if empty → error + re-prompt; else store `context.user_data["task_name"]` + ask cycle, return `ASK_CYCLE`
  - [x] `receive_cycle(update, context) -> int`: regex extract leading integer; if ≤ 0 → error + re-prompt; else store `context.user_data["cycle_days"]` + ask date, return `ASK_DATE`
  - [x] `receive_date(update, context) -> int`: parse DD/MM/YYYY; if invalid → error + re-prompt; else call `task_repo.create_task()`, send confirmation (HTML parse_mode, `html.escape(name)` for safety), return `ConversationHandler.END`
  - [x] `cancel(update, context) -> int`: reply "Đã hủy. Task không được lưu.", return `ConversationHandler.END`
  - [x] `build_add_conversation() -> ConversationHandler`: assemble and return the handler (see exact structure in Dev Notes)

- [x] Task 3 — Wire into main.py (AC: 1)
  - [x] In `main()`: change `open_db()` (schema-init-only call) to `app_db = open_db()` — keep connection alive
  - [x] After `ApplicationBuilder().token(token).build()`, add `application.bot_data["db"] = app_db`
  - [x] Import `build_add_conversation` from `homekeeper.bot.task_handlers`
  - [x] Register: `application.add_handler(build_add_conversation())` — BEFORE `run_polling()`
  - [x] Keep existing `CommandHandler("start", start_handler)` registration unchanged

- [x] Task 4 — Verification (AC: 1–7)
  - [x] Syntax check (ast.parse) all 3 changed/new Python files
  - [x] Verify AD-1: task_handlers.py imports only bot/, db/, stdlib — no upward import from db/ back to bot/
  - [x] Verify AD-4: no HTTP client anywhere in codebase
  - [x] Verify task_repo.py uses `conn` passed in (no direct `open_db()` call inside repo — connection comes from caller)
  - [x] Verify confirmation message uses `html.escape(name)` + `parse_mode="HTML"`
  - [x] Verify cancel returns `ConversationHandler.END` (not just `None`)

## Dev Notes

### Stack (carry-forward from Story 1.1)

- **Python:** ≥ 3.12 — `str | None` type hints, not `Optional[str]`
- **python-telegram-bot:** ≥ 21.0 — fully async, `ApplicationBuilder`, all handlers are `async def`
- **SQLite:** bundled — `conn.row_factory = sqlite3.Row` already set by `open_db()`

### Completed Files From Story 1.1 (read before touching)

All files below exist and are **correct** — do not re-implement or restructure them:

```
main.py                         ← UPDATE (3 targeted edits)
homekeeper/bot/__init__.py      ← READ ONLY (admin_only decorator — apply unchanged)
homekeeper/db/connection.py     ← READ ONLY (open_db() — call it, don't modify)
homekeeper/db/schema.sql        ← READ ONLY (TASK table already defined)
```

**Story 1.1 review learnings to apply here:**
- Always use `update.effective_message` not `update.message` (works for both messages and callback queries)
- Always use `update.effective_user` (not `update.message.from_user`) and guard for `None` where applicable
- `admin_only` decorator: apply it to entry-point handler only (`add_start`), not to state handlers (ConversationHandler tracks per-user state — state handlers are only reachable by the user who entered the conversation)
- `open_db()` returns a connection with `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `row_factory=sqlite3.Row` already set

### DB Connection Pattern for Handlers (AD-5)

Story 1.1 used `open_db()` for schema init only (connection discarded). Story 1.2 needs a real persistent connection for handlers. **The correct pattern:**

```python
# In main() — one connection for the entire PTB thread lifetime
app_db = open_db()          # schema init + persistent PTB-thread connection
application = ApplicationBuilder().token(token).build()
application.bot_data["db"] = app_db   # store for handler access
```

```python
# In any handler that needs DB
conn = context.application.bot_data["db"]
task_repo.create_task(conn, name, cycle_days, next_due_date_str)
```

**Why this pattern:** AD-5 says "each thread holds its own connection." PTB's event loop (polling) runs in the main thread. `app_db` is opened in that thread and used only in that thread — correct. The scheduler thread (Story 2.1) will open its own separate connection. Never pass `app_db` to another thread.

### task_repo.py — Exact Interface

```python
# homekeeper/db/task_repo.py
import sqlite3
from datetime import datetime


def create_task(
    conn: sqlite3.Connection,
    name: str,
    cycle_days: int,
    next_due_date: str,   # ISO-8601 date string "YYYY-MM-DD"
) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds")
    cursor = conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at) VALUES (?, ?, ?, ?)",
        (name, cycle_days, next_due_date, now),
    )
    conn.commit()
    return cursor.lastrowid
```

**Notes:**
- `datetime.utcnow()` for `created_at` — always UTC internally (per architecture conventions)
- `next_due_date` arrives as `date.isoformat()` from the handler → "YYYY-MM-DD" string
- `conn.commit()` required; `open_db()` does not auto-commit
- Return `lastrowid` (may be used by future stories for edit/delete)
- Story 1.3 and 1.4 will add `get_all_tasks()`, `update_task()`, `delete_task()` to this file — leave room

### task_handlers.py — Full ConversationHandler Structure

```python
# homekeeper/bot/task_handlers.py
import html
import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from homekeeper.bot import admin_only
from homekeeper.db import task_repo

logger = logging.getLogger(__name__)

ASK_NAME, ASK_CYCLE, ASK_DATE = range(3)


@admin_only
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text(
        "Tên công việc là gì? (ví dụ: Thay lõi lọc nước)"
    )
    return ASK_NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if not name:
        await update.effective_message.reply_text(
            "Tên không được để trống. Nhập lại tên công việc:"
        )
        return ASK_NAME
    context.user_data["task_name"] = name
    await update.effective_message.reply_text(
        "Chu kỳ lặp lại? (ví dụ: 30 ngày, 90 ngày, 180 ngày)"
    )
    return ASK_CYCLE


async def receive_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    match = re.match(r"(\d+)", text)
    cycle_days = int(match.group(1)) if match else 0
    if cycle_days <= 0:
        await update.effective_message.reply_text(
            "Chu kỳ phải là số nguyên dương (ví dụ: 30 hoặc 30 ngày). Nhập lại:"
        )
        return ASK_CYCLE
    context.user_data["cycle_days"] = cycle_days
    await update.effective_message.reply_text(
        "Ngày đến hạn tiếp theo? (định dạng DD/MM/YYYY)"
    )
    return ASK_DATE


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    try:
        due_date = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        await update.effective_message.reply_text(
            "Ngày không hợp lệ. Vui lòng nhập theo định dạng DD/MM/YYYY "
            "(ví dụ: 25/06/2026):"
        )
        return ASK_DATE

    name = context.user_data["task_name"]
    cycle_days = context.user_data["cycle_days"]

    conn = context.application.bot_data["db"]
    task_repo.create_task(conn, name, cycle_days, due_date.isoformat())

    reminder_date = due_date - timedelta(days=1)
    await update.effective_message.reply_text(
        f"✅ Đã thêm: <b>{html.escape(name)}</b> — "
        f"đến hạn {due_date.strftime('%d/%m/%Y')}, "
        f"nhắc trước 1 ngày vào {reminder_date.strftime('%d/%m/%Y')}.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_message.reply_text("Đã hủy. Task không được lưu.")
    return ConversationHandler.END


def build_add_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_CYCLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cycle)],
            ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
```

### main.py — Exact Changes Required

The current `main.py` (after Story 1.1 patches) has this in `main()`:

```python
try:
    open_db()  # schema init; connection intentionally discarded after DDL
except Exception as exc:
    logger.error("DB initialisation failed: %s", exc)
    sys.exit(1)

application = ApplicationBuilder().token(token).build()
application.add_handler(CommandHandler("start", start_handler))
```

**Change 1:** Capture the connection and store in bot_data:
```python
try:
    app_db = open_db()   # schema init + persistent PTB-thread connection
except Exception as exc:
    logger.error("DB initialisation failed: %s", exc)
    sys.exit(1)

application = ApplicationBuilder().token(token).build()
application.bot_data["db"] = app_db                       # ← ADD THIS LINE
application.add_handler(build_add_conversation())          # ← ADD THIS LINE (before start handler)
application.add_handler(CommandHandler("start", start_handler))
```

**Change 2:** Add import at the top of the file (after existing imports):
```python
from homekeeper.bot.task_handlers import build_add_conversation
```

**No other changes to main.py.** The `# TODO Story 2.1` comment stays. The start_handler and all other existing code stays.

### ConversationHandler Registration Order

Register `build_add_conversation()` **before** the bare `CommandHandler("start", ...)`. ConversationHandlers have higher priority in PTB's handler stack when registered first. This ensures `/cancel` inside the add-flow is caught by the ConversationHandler's fallbacks before any other handler sees it.

### Input Parsing Details

**Cycle parsing (`receive_cycle`):**
- `re.match(r"(\d+)", text)` — matches the first sequence of digits
- Handles: "30", "30 ngày", "30 days", " 30 ngày ", "30ngày"
- Rejects: "abc", "", "0 ngày" (cycle_days = 0 fails validation)
- `int(match.group(1))` is safe because `\d+` always parses to int

**Date parsing (`receive_date`):**
- `datetime.strptime(text, "%d/%m/%Y")` — strict format match
- `ValueError` on any malformed input (wrong separator, wrong year length, impossible dates)
- `.date()` extracts the `date` part; `.isoformat()` → "YYYY-MM-DD" for SQLite storage
- Display format uses `.strftime('%d/%m/%Y')` → "25/06/2026" for user messages

**Confirmation message HTML escaping:**
- `html.escape(name)` prevents task names with `<`, `>`, `&` from breaking the HTML parse
- Example: task name `"Vệ sinh máy lọc <Panasonic>"` → `"Vệ sinh máy lọc &lt;Panasonic&gt;"` in the bot message, displayed correctly by Telegram

### Architecture Constraints Checklist (AD-1 through AD-8)

| Rule | Story 1.2 compliance |
|------|--------------------|
| AD-1 Downward-only imports | task_handlers.py → `homekeeper.bot` (admin_only), `homekeeper.db.task_repo` ✓; task_repo.py → stdlib only ✓; no upward imports from db/ back to bot/ ✓ |
| AD-2 No shared memory | `app_db` connection never passed to scheduler thread; stored in bot_data accessible only to PTB handlers ✓ |
| AD-3 Domain pure Python | No domain logic in this story — scheduling.py used in Story 2.4 ✓ |
| AD-4 No HTTP client | Only `telegram.ext` for Telegram messages — no external calls ✓ |
| AD-5 WAL + one conn/thread | `app_db` opened in main thread, used only in PTB handlers (same thread) ✓ |
| AD-7 In-memory conversation state | `ConversationHandler` default in-memory state; `context.user_data` for temporary name/cycle/date ✓ |

### Dates & Times Convention (from architecture)

- Store `created_at` as `datetime.utcnow().isoformat(timespec="seconds")` → `"2026-06-25T10:30:00"` (UTC)
- Store `next_due_date` as `date.isoformat()` → `"2026-06-25"` (UTC, but dates are timezone-agnostic here)
- Display to user as `date.strftime('%d/%m/%Y')` → `"25/06/2026"` (Vietnam-friendly format, not UTC+7 conversion needed for dates)

### File List for This Story

```
homekeeper/bot/task_handlers.py    ← NEW
homekeeper/db/task_repo.py         ← NEW
main.py                            ← UPDATE (3 targeted changes: capture open_db() return, bot_data["db"], import + register handler)
```

No other files are created or modified.

### References

- [Source: planning-artifacts/epics.md — Story 1.2 Acceptance Criteria]
- [Source: planning-artifacts/architecture/ARCHITECTURE-SPINE.md — AD-1, AD-2, AD-4, AD-5, AD-7, Structural Seed]
- [Source: implementation-artifacts/1-1-bot-foundation-and-admin-auth.md — Review Findings (effective_message, admin_only pattern)]

### Review Findings

- [x] [Review][Patch] receive_date: access user_data with .get() guards — KeyError if user_data lacks task_name/cycle_days (stale/corrupted state) [homekeeper/bot/task_handlers.py:72-73]
- [x] [Review][Patch] task_repo: replace datetime.utcnow() with datetime.now(timezone.utc) — utcnow() deprecated Python 3.12, removed in 3.14 [homekeeper/db/task_repo.py:11]
- [x] [Review][Patch] receive_name: add MAX_NAME_LEN cap (200 chars) — uncapped name >4096 chars causes unhandled Telegram BadRequest crash [homekeeper/bot/task_handlers.py:35]
- [x] [Review][Patch] receive_date: wrap create_task() in try/except sqlite3.Error — unhandled OperationalError (disk full) leaves user with no feedback [homekeeper/bot/task_handlers.py:74]
- [x] [Review][Defer] SQLite check_same_thread: safe with default concurrent_updates=False; risk only if concurrent_updates=True enabled later [main.py:52] — deferred, pre-existing design
- [x] [Review][Defer] create_task commits unconditionally — fine for v1 single-op; revisit if multi-op transactions needed in later stories [homekeeper/db/task_repo.py:16] — deferred, pre-existing
- [x] [Review][Defer] No upper bound on cycle_days — OverflowError risk in scheduler; Story 2 should add validation [homekeeper/bot/task_handlers.py:49] — deferred, story 2.x concern
- [x] [Review][Defer] admin_only returns None not ConversationHandler.END — entry point rejection doesn't start conversation anyway; acceptable v1 behavior [homekeeper/bot/__init__.py] — deferred, pre-existing
- [x] [Review][Defer] receive_date doesn't clear user_data keys — harmless, keys always overwritten by receive_name/receive_cycle before reuse [homekeeper/bot/task_handlers.py:74] — deferred, cosmetic
- [x] [Review][Defer] Past dates accepted without warning — not in spec; scheduler Story 2 handles overdue — deferred, out of scope
- [x] [Review][Defer] No conversation_timeout — personal single-user bot; memory impact negligible [homekeeper/bot/task_handlers.py:93] — deferred, pre-existing
- [x] [Review][Defer] OverflowError on date.min - timedelta(1) (01/01/0001 input) — extremely unlikely user input — deferred, impractical edge case
- [x] [Review][Defer] "db" key absent from bot_data — impossible in production; main() sys.exit(1) on open_db() failure — deferred, not reachable

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Syntax validation: all 3 Python files parse cleanly (ast.parse)
- AD-1 verified: task_repo.py has no bot/ or scheduler/ imports
- AD-4 verified: no HTTP client in codebase (grep clean)
- task_repo conn pattern verified: no open_db() call inside repo; uses passed-in conn
- HTML escaping verified: html.escape(name) + parse_mode="HTML" present in receive_date
- cancel END verified: returns ConversationHandler.END

### Completion Notes List

- DB connection stored in `application.bot_data["db"]` — one persistent PTB-thread connection (AD-5); handlers access via `context.application.bot_data["db"]`
- `@admin_only` applied to entry point `add_start` only; state handlers not decorated (ConversationHandler per-user keying ensures non-admins cannot reach state handlers)
- Cycle parsing uses `re.match(r"(\d+)", text)` — accepts "30", "30 ngày", "30 days", "30ngày"
- Date stored as `date.isoformat()` ("YYYY-MM-DD") in SQLite; displayed as `strftime('%d/%m/%Y')` to user
- Confirmation message uses `parse_mode="HTML"` + `html.escape(name)` to safely handle task names with `<`, `>`, `&`
- `build_add_conversation()` registered before `CommandHandler("start", ...)` so ConversationHandler has priority in PTB handler stack

### File List

- homekeeper/bot/task_handlers.py (NEW)
- homekeeper/db/task_repo.py (NEW)
- main.py (UPDATED)
