---
baseline_commit: NO_VCS
---

# Story 1.3: View Task List

Status: done

## Story

As a Admin,
I want to see all my scheduled tasks sorted by due date,
So that I know what's coming up and what's overdue.

## Acceptance Criteria

1. **[AC-1] Non-empty list:** Given Admin gửi `/list`, when có ít nhất một Task trong database, then bot trả về danh sách tất cả Task sort theo `next_due_date` tăng dần, mỗi Task hiển thị: tên, ngày đến hạn, số ngày còn lại (hoặc số ngày đã trễ).

2. **[AC-2] Overdue marking:** Given có Task với `next_due_date` < ngày hôm nay, when Admin xem `/list`, then Task đó được đánh dấu ⚠️ Quá hạn và hiển thị số ngày đã trễ.

3. **[AC-3] Empty list:** Given Admin gửi `/list`, when không có Task nào trong database, then bot trả về: "Chưa có công việc nào. Dùng /add để thêm."

## Tasks / Subtasks

- [x] Task 1 — DB layer: add get_all_tasks to task_repo (AC: 1, 2)
  - [x] Add `get_all_tasks(conn: sqlite3.Connection) -> list` to `homekeeper/db/task_repo.py`
  - [x] Query: `SELECT id, name, cycle_days, next_due_date, created_at FROM TASK ORDER BY next_due_date ASC`
  - [x] Return `cursor.fetchall()` — rows are `sqlite3.Row` objects (column access by name) because `open_db()` sets `row_factory = sqlite3.Row`

- [x] Task 2 — Bot handler: list_handler (AC: 1, 2, 3)
  - [x] Add `list_handler(update, context)` to `homekeeper/bot/task_handlers.py`
  - [x] Decorate with `@admin_only`
  - [x] Get conn: `conn = context.application.bot_data["db"]`
  - [x] Call `task_repo.get_all_tasks(conn)` wrapped in try/except
  - [x] If empty → reply "Chưa có công việc nào. Dùng /add để thêm." (plain text)
  - [x] If non-empty → build numbered HTML list (see exact format in Dev Notes), send with `parse_mode="HTML"`
  - [x] Per-task status: `delta = (due_date - today).days`: if `< 0` → `⚠️ Quá hạn {abs(delta)} ngày`; if `== 0` → `📅 Đến hạn hôm nay`; if `> 0` → `còn {delta} ngày`
  - [x] Use `html.escape(row["name"])` in message body

- [x] Task 3 — Wire into main.py (AC: 1)
  - [x] Import `list_handler` from `homekeeper.bot.task_handlers`
  - [x] Register: `application.add_handler(CommandHandler("list", list_handler))`
  - [x] Keep all existing handlers unchanged

- [x] Task 4 — Verification (AC: 1–3)
  - [x] Syntax check (ast.parse) all 3 changed files
  - [x] Verify AD-1: no upward import from task_repo.py to bot/
  - [x] Verify `html.escape` used on task name in message
  - [x] Verify `@admin_only` on `list_handler`
  - [x] Verify `get_all_tasks` uses `ORDER BY next_due_date ASC`

### Review Findings

- [x] [Review][Patch] Non-deterministic sort order for same-date tasks [homekeeper/db/task_repo.py: get_all_tasks] — `ORDER BY next_due_date ASC` has no tiebreaker; tasks sharing a due date can renumber between `/list` calls. Fix: `ORDER BY next_due_date ASC, id ASC`
- [x] [Review][Patch] `date.fromisoformat()` crash on malformed `next_due_date` — unhandled `ValueError` inside loop body propagates uncaught; user gets no response at all. Fix: wrap loop body's `fromisoformat` call in `try/except (ValueError, TypeError)` and skip/log bad rows [homekeeper/bot/task_handlers.py: list_handler]
- [x] [Review][Patch] Final `reply_text` not wrapped in try/except — story notes claimed the existing try/except catches Telegram's `BadRequest` on message-too-long, but it only wraps `get_all_tasks`; any Telegram API error on the main reply leaves user with no response [homekeeper/bot/task_handlers.py: list_handler]
- [x] [Review][Defer] Message length overflow / pagination — 4096-char limit hit at ~16 worst-case tasks; explicitly deferred in story notes; personal bot scope [homekeeper/bot/task_handlers.py: list_handler] — deferred, pre-existing design decision
- [x] [Review][Defer] `@admin_only` missing on ConversationHandler state callbacks — pre-existing from Story 1.2, not introduced by this story; `/cancel` accessible to any user without auth check [homekeeper/bot/task_handlers.py] — deferred, pre-existing
- [x] [Review][Defer] Scheduler thread DB connection crash — Story 2.1 must call `open_db()` independently; `check_same_thread=True` default will raise ProgrammingError if shared [main.py, homekeeper/db/connection.py] — deferred, Story 2.1 scope
- [x] [Review][Defer] Test gaps for corrupt date / overflow scenarios — derivative of patches P2/P3; low priority for personal bot [tests/] — deferred, pre-existing

## Dev Notes

### Stack (carry-forward)

- Python ≥ 3.12, PTB ≥ 21.0 async, SQLite bundled
- All handlers are `async def`; use `update.effective_message` (not `update.message`)
- `context.application.bot_data["db"]` is the PTB-thread DB connection (set in `main()` since Story 1.2)

### Files Being Modified — Read Before Touching

```
homekeeper/db/task_repo.py      ← UPDATE (add get_all_tasks)
homekeeper/bot/task_handlers.py ← UPDATE (add list_handler)
main.py                         ← UPDATE (import + register CommandHandler("list", ...))
```

**Current state of `task_repo.py`** (Story 1.2 final, after review patches):
```python
import sqlite3
from datetime import datetime, timezone

def create_task(conn, name, cycle_days, next_due_date) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at) VALUES (?, ?, ?, ?)",
        (name, cycle_days, next_due_date, now),
    )
    conn.commit()
    return cursor.lastrowid
```
→ Add `get_all_tasks()` below `create_task()`. Do NOT modify `create_task()`.

**Current state of `task_handlers.py`** (Story 1.2 final, after review patches):
- Has `add_start`, `receive_name`, `receive_cycle`, `receive_date`, `cancel`, `build_add_conversation()`
- Has `MAX_TASK_NAME_LEN = 200` constant
- Imports: `html`, `logging`, `re`, `datetime`, `timedelta`, `Update`, `CommandHandler`, `ConversationHandler`, `ContextTypes`, `MessageHandler`, `filters`, `admin_only`, `task_repo`
→ Add `list_handler` as a new standalone function. Add `date` to the datetime import. Do NOT modify existing functions.

**Current state of `main.py`** (Story 1.2 final):
```python
from homekeeper.bot import admin_only
from homekeeper.bot.task_handlers import build_add_conversation
from homekeeper.db.connection import open_db
...
application.add_handler(build_add_conversation())
application.add_handler(CommandHandler("start", start_handler))
```
→ Add `list_handler` to the import line and register `CommandHandler("list", list_handler)`.

### get_all_tasks — Exact Implementation

```python
def get_all_tasks(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK ORDER BY next_due_date ASC"
    )
    return cursor.fetchall()
```

Return type is `list[sqlite3.Row]`. Rows support column access by name (`row["name"]`, `row["next_due_date"]`) because `open_db()` sets `conn.row_factory = sqlite3.Row`.

**Note for Story 1.4:** `get_all_tasks()` returns rows in `next_due_date ASC` order. Story 1.4 will display a numbered selection list for edit/delete using the same ordering — reuse this function directly.

### list_handler — Exact Implementation

```python
@admin_only
async def list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.application.bot_data["db"]
    try:
        rows = task_repo.get_all_tasks(conn)
    except Exception as exc:
        logger.error("Failed to load tasks: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách. Vui lòng thử lại sau."
        )
        return

    if not rows:
        await update.effective_message.reply_text(
            "Chưa có công việc nào. Dùng /add để thêm."
        )
        return

    today = date.today()
    lines = [f"📋 <b>Danh sách công việc bảo trì</b> ({len(rows)} công việc):\n"]
    for i, row in enumerate(rows, 1):
        due_date = date.fromisoformat(row["next_due_date"])
        delta = (due_date - today).days
        if delta < 0:
            status = f"⚠️ Quá hạn {abs(delta)} ngày"
        elif delta == 0:
            status = "📅 Đến hạn hôm nay"
        else:
            status = f"còn {delta} ngày"
        lines.append(
            f"{i}. <b>{html.escape(row['name'])}</b> — "
            f"{due_date.strftime('%d/%m/%Y')} ({status})"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
    )
```

**Import change needed in task_handlers.py:**
```python
# Change:
from datetime import datetime, timedelta
# To:
from datetime import date, datetime, timedelta
```

### main.py — Exact Change

```python
# Change this import line:
from homekeeper.bot.task_handlers import build_add_conversation
# To:
from homekeeper.bot.task_handlers import build_add_conversation, list_handler

# Add this handler registration (after build_add_conversation, before or after start):
application.add_handler(CommandHandler("list", list_handler))
```

### "Today" Date Assumption

`date.today()` returns the **local machine date**. This bot runs on the admin's personal machine (Vietnam, UTC+7). So `date.today()` correctly returns the Vietnam date for comparison against due dates stored as ISO-8601.

If the bot is ever moved to a UTC server, this comparison would be off by up to 7 hours near midnight. For v1 personal deployment, `date.today()` is correct.

### Message Length Safety

With `MAX_TASK_NAME_LEN = 200` (enforced in Story 1.2), each task line is at most ~240 chars. Telegram's limit is 4096 chars, so the list can hold ~16 tasks safely. For a personal bot, this is more than sufficient. If the list exceeds 4096 chars in a future scenario, Telegram will raise `BadRequest` — the try/except in `list_handler` catches this. Pagination is deferred.

### Architecture Constraints

| Rule | Story 1.3 compliance |
|------|--------------------|
| AD-1 Downward-only imports | `list_handler` imports `task_repo` (db/) — downward ✓; `task_repo.get_all_tasks` imports only stdlib ✓ |
| AD-4 No HTTP client | Only Telegram messages — no external calls ✓ |
| AD-5 One conn/thread | Reads from `bot_data["db"]` — same PTB main-thread connection ✓ |

### File List for This Story

```
homekeeper/db/task_repo.py         ← UPDATE (add get_all_tasks)
homekeeper/bot/task_handlers.py    ← UPDATE (add list_handler, add date to imports)
main.py                            ← UPDATE (import list_handler, register CommandHandler("list", ...))
```

### References

- [Source: planning-artifacts/epics.md — Story 1.3 Acceptance Criteria]
- [Source: planning-artifacts/architecture/ARCHITECTURE-SPINE.md — AD-1, AD-5]
- [Source: implementation-artifacts/1-2-add-maintenance-task.md — task_repo patterns, bot_data["db"], html.escape, admin_only]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- pytest install required (telegram module missing); resolved by running `pip3 install python-telegram-bot python-dotenv`

### Completion Notes List

- Implemented `get_all_tasks(conn)` in task_repo.py: SELECT all TASK rows ORDER BY next_due_date ASC; returns list[sqlite3.Row]
- Implemented `list_handler` in task_handlers.py: @admin_only, reads from bot_data["db"], builds numbered HTML list with per-task delta status (overdue / today / future), uses html.escape for safety
- Updated main.py: imported list_handler, registered CommandHandler("list", list_handler)
- All 3 ACs verified: empty state (AC-3), overdue marking ⚠️ (AC-2), sorted list (AC-1)
- 12 pytest tests written and passing: 5 for get_all_tasks (repo layer) + 7 for list_handler (bot handler)

### File List

- homekeeper/db/task_repo.py (updated — added get_all_tasks)
- homekeeper/bot/task_handlers.py (updated — added list_handler, added date to imports)
- main.py (updated — imported list_handler, registered CommandHandler("list", list_handler))
- tests/__init__.py (new)
- tests/test_task_repo_list.py (new — 5 tests for get_all_tasks)
- tests/test_list_handler.py (new — 7 tests for list_handler)
