# Story 1.4: Edit & Delete Task

Status: done

## Story

As a Admin,
I want to edit or delete an existing task,
So that I can keep my schedule accurate when things change.

## Acceptance Criteria

1. **[AC-1] Edit — show selection list:** Given Admin gửi `/edit`, when có Task trong database, then bot hiển thị danh sách Task có đánh số (same order as `/list`) và hỏi: "Chọn số thứ tự Task muốn sửa:"

2. **[AC-2] Edit — field update with keep-old:** Given Admin chọn một Task hợp lệ, when bot hiển thị từng trường với giá trị hiện tại, then Admin có thể sửa tên, Cycle, hoặc ngày đến hạn; trường nào bỏ trống hoặc gửi "-" = giữ nguyên giá trị cũ.

3. **[AC-3] Edit — Cycle change does not recalculate next_due_date:** Given Admin thay đổi Cycle của Task, when lưu thay đổi, then `next_due_date` vẫn giữ nguyên (Cycle mới chỉ ảnh hưởng đến lần reschedule tiếp theo sau khi hoàn thành); ngày Reminder = `next_due_date − 1` được tính từ ngày hạn hiện tại.

4. **[AC-4] Delete — confirm and execute:** Given Admin gửi `/delete`, when Admin chọn Task và xác nhận "Có", then Task bị xóa khỏi database; bot xác nhận: "✅ Đã xóa: **[tên Task]**"

5. **[AC-5] Delete — cancel on "Không":** Given Admin chọn `/delete` nhưng trả lời "Không" (hoặc bất kỳ văn bản nào khác không phải "Có"), when bot nhận input, then Task không bị xóa và bot thông báo: "Đã hủy xóa."

6. **[AC-6] Empty list guards:** Given Admin gửi `/edit` hoặc `/delete`, when không có Task nào trong database, then bot trả về thông báo tương ứng và không mở ConversationHandler.

## Tasks / Subtasks

- [x] Task 1 — DB layer: add get_task_by_id, update_task, delete_task to task_repo (AC: 1–5)
  - [x] Add `get_task_by_id(conn, task_id: int) -> sqlite3.Row | None` — `SELECT ... FROM TASK WHERE id = ?`
  - [x] Add `update_task(conn, task_id: int, name: str, cycle_days: int, next_due_date: str) -> None` — `UPDATE TASK SET ... WHERE id = ?`, then `conn.commit()`
  - [x] Add `delete_task(conn, task_id: int) -> None` — `DELETE FROM TASK WHERE id = ?`, then `conn.commit()`
  - [x] All three must NOT import anything from `homekeeper.bot` (AD-1)

- [x] Task 2 — Bot layer: edit conversation (AC: 1, 2, 3)
  - [x] Add state constants: `EDIT_SELECT, EDIT_NAME, EDIT_CYCLE, EDIT_DATE = range(3, 7)`
  - [x] Add helper: `_is_keep_old(text: str) -> bool` — returns True if text.strip() is `""` or `"-"`
  - [x] Add `edit_start` (decorated `@admin_only`): fetch all tasks; if empty → reply "Chưa có công việc nào để sửa. Dùng /add để thêm." return END; else display numbered list + prompt "Chọn số thứ tự Task muốn sửa: (hoặc /cancel để hủy)", store `context.user_data["edit_task_ids"]`, return `EDIT_SELECT`
  - [x] Add `receive_edit_select`: parse int, validate 1–N; on invalid → re-prompt; on valid → fetch task by id via `get_task_by_id`, store `context.user_data["edit_task"]`, prompt name field with current value, return `EDIT_NAME`
  - [x] Add `receive_edit_name`: if `_is_keep_old(text)` → use old name; else strip + validate len ≤ 200 (re-prompt if too long); store `context.user_data["edit_name"]`, prompt cycle field with current value, return `EDIT_CYCLE`
  - [x] Add `receive_edit_cycle`: if `_is_keep_old(text)` → use old cycle; else parse int via `re.match(r"(\d+)", text)`, validate > 0 (re-prompt if invalid); store `context.user_data["edit_cycle"]`, prompt date field with current value, return `EDIT_DATE`
  - [x] Add `receive_edit_date`: if `_is_keep_old(text)` → use old date; else parse DD/MM/YYYY (re-prompt on invalid); call `update_task(conn, task_id, name, cycle_days, next_due_date)`; compute `reminder_date = due_date - timedelta(days=1)`; reply "✅ Đã cập nhật: **[name]** — đến hạn [DD/MM/YYYY], nhắc trước 1 ngày vào [DD/MM/YYYY]." with `parse_mode="HTML"` and `html.escape(name)`; return `END`
  - [x] Add `edit_cancel`: reply "Đã hủy sửa.", return `END`
  - [x] Add `build_edit_conversation()` returning a `ConversationHandler`

- [x] Task 3 — Bot layer: delete conversation (AC: 4, 5, 6)
  - [x] Add state constants: `DELETE_SELECT, DELETE_CONFIRM = range(7, 9)`
  - [x] Add `delete_start` (decorated `@admin_only`): fetch all tasks; if empty → reply "Chưa có công việc nào để xóa.", return END; else display numbered list + prompt "Chọn số thứ tự Task muốn xóa: (hoặc /cancel để hủy)", store `context.user_data["delete_task_ids"]`, return `DELETE_SELECT`
  - [x] Add `receive_delete_select`: parse int, validate range; on valid → `get_task_by_id`, store `context.user_data["delete_task"]`; prompt "Bạn có chắc muốn xóa **[name]**? Trả lời 'Có' để xác nhận hoặc 'Không' để hủy." (`parse_mode="HTML"`, `html.escape(name)`), return `DELETE_CONFIRM`
  - [x] Add `receive_delete_confirm`: if text.strip().lower() == "có" → `delete_task(conn, task_id)`, reply "✅ Đã xóa: **[name]**" (`parse_mode="HTML"`, `html.escape(name)`), return END; else → reply "Đã hủy xóa.", return END
  - [x] Add `delete_cancel`: reply "Đã hủy xóa.", return `END`
  - [x] Add `build_delete_conversation()` returning a `ConversationHandler`

- [x] Task 4 — Wire into main.py (AC: 1, 4)
  - [x] Import `build_edit_conversation`, `build_delete_conversation` from `homekeeper.bot.task_handlers`
  - [x] Register: `application.add_handler(build_edit_conversation())`
  - [x] Register: `application.add_handler(build_delete_conversation())`
  - [x] Keep ALL existing handlers unchanged

- [x] Task 5 — Verification (AC: 1–6)
  - [x] Syntax check (ast.parse) all changed files
  - [x] Verify `@admin_only` on `edit_start` and `delete_start`
  - [x] Verify AD-1: task_repo.py imports only stdlib
  - [x] Verify `html.escape` on task name in all HTML messages
  - [x] Verify `conn.commit()` called in `update_task` and `delete_task`
  - [x] Verify state ranges don't overlap: 0–2 (add), 3–6 (edit), 7–8 (delete)

## Dev Notes

### Stack (carry-forward)

- Python ≥ 3.12, PTB ≥ 21.0 async, SQLite bundled
- All handlers are `async def`; use `update.effective_message` (not `update.message`)
- `context.application.bot_data["db"]` is the shared PTB-thread DB connection
- `@admin_only` from `homekeeper.bot` must decorate all entry-point handlers
- `html.escape()` + `parse_mode="HTML"` for all messages containing user-supplied data
- Wrap DB calls in `try/except Exception`; wrap final `reply_text` calls in `try/except Exception`
- `.get()` with guards when reading from `context.user_data`

### Files Being Modified — Read Before Touching

```
homekeeper/db/task_repo.py         ← UPDATE (add get_task_by_id, update_task, delete_task)
homekeeper/bot/task_handlers.py    ← UPDATE (add edit + delete states, handlers, builders)
main.py                            ← UPDATE (import + register build_edit_conversation, build_delete_conversation)
```

### Current State of task_repo.py (Story 1.3 final)

```python
import sqlite3
from datetime import datetime, timezone


def get_all_tasks(conn: sqlite3.Connection) -> list:
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK ORDER BY next_due_date ASC, id ASC"
    )
    return cursor.fetchall()


def create_task(conn, name, cycle_days, next_due_date) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO TASK (name, cycle_days, next_due_date, created_at) VALUES (?, ?, ?, ?)",
        (name, cycle_days, next_due_date, now),
    )
    conn.commit()
    return cursor.lastrowid
```

→ Append three new functions AFTER `create_task`. Do NOT modify `get_all_tasks` or `create_task`.

### Current State of task_handlers.py (Story 1.3 final, post-review)

Key existing pieces:
- Imports: `html`, `logging`, `re`, `date`, `datetime`, `timedelta`, PTB types, `admin_only`, `task_repo`
- `ASK_NAME, ASK_CYCLE, ASK_DATE = range(3)` (0, 1, 2)
- `MAX_TASK_NAME_LEN = 200`
- `list_handler`, `add_start`, `receive_name`, `receive_cycle`, `receive_date`, `cancel`, `build_add_conversation`

→ Add NEW states and functions. State integers must NOT overlap with existing ones (0, 1, 2). Use range(3, 7) for edit and range(7, 9) for delete.
→ The existing `cancel` function is the fallback for `build_add_conversation()` only. Add separate `edit_cancel` and `delete_cancel`.
→ Do NOT modify any existing function.

### Current State of main.py (Story 1.3 final)

```python
from homekeeper.bot.task_handlers import build_add_conversation, list_handler
...
application.add_handler(build_add_conversation())
application.add_handler(CommandHandler("list", list_handler))
application.add_handler(CommandHandler("start", start_handler))
```

→ Add to the import line and add handler registrations.

### get_task_by_id — Exact Implementation

```python
def get_task_by_id(conn: sqlite3.Connection, task_id: int):
    cursor = conn.execute(
        "SELECT id, name, cycle_days, next_due_date, created_at "
        "FROM TASK WHERE id = ?",
        (task_id,),
    )
    return cursor.fetchone()  # returns sqlite3.Row or None
```

### update_task — Exact Implementation

```python
def update_task(
    conn: sqlite3.Connection,
    task_id: int,
    name: str,
    cycle_days: int,
    next_due_date: str,
) -> None:
    conn.execute(
        "UPDATE TASK SET name = ?, cycle_days = ?, next_due_date = ? WHERE id = ?",
        (name, cycle_days, next_due_date, task_id),
    )
    conn.commit()
```

### delete_task — Exact Implementation

```python
def delete_task(conn: sqlite3.Connection, task_id: int) -> None:
    conn.execute("DELETE FROM TASK WHERE id = ?", (task_id,))
    conn.commit()
```

### State Constants — Exact Values

```python
# Existing (do not change)
ASK_NAME, ASK_CYCLE, ASK_DATE = range(3)   # 0, 1, 2

# New for edit conversation
EDIT_SELECT, EDIT_NAME, EDIT_CYCLE, EDIT_DATE = range(3, 7)  # 3, 4, 5, 6

# New for delete conversation
DELETE_SELECT, DELETE_CONFIRM = range(7, 9)  # 7, 8
```

### Helper Function

```python
def _is_keep_old(text: str) -> bool:
    return text.strip() in ("", "-")
```

### Numbered List Display (reused for edit and delete entry points)

Use `get_all_tasks(conn)` (already exists, ORDER BY next_due_date ASC, id ASC). Store the IDs in `user_data` at display time.

```python
rows = task_repo.get_all_tasks(conn)
if not rows:
    await update.effective_message.reply_text("Chưa có công việc nào để sửa. Dùng /add để thêm.")
    return ConversationHandler.END

today = date.today()
lines = ["📋 Chọn số thứ tự Task muốn sửa:\n"]
for i, row in enumerate(rows, 1):
    try:
        due_date = date.fromisoformat(row["next_due_date"])
        delta = (due_date - today).days
        if delta < 0:
            status = f"⚠️ Quá hạn {abs(delta)} ngày"
        elif delta == 0:
            status = "📅 Đến hạn hôm nay"
        else:
            status = f"còn {delta} ngày"
        date_display = due_date.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        status = "⚠️ Ngày không hợp lệ"
        date_display = html.escape(str(row["next_due_date"]))
    lines.append(
        f"{i}. <b>{html.escape(row['name'])}</b> — {date_display} ({status})"
    )
lines.append("\n(hoặc /cancel để hủy)")

context.user_data["edit_task_ids"] = [row["id"] for row in rows]
await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
return EDIT_SELECT
```

For delete, replace `"edit_task_ids"` with `"delete_task_ids"` and adjust the heading.

### Number Selection Pattern (edit and delete share the same logic)

```python
text = update.effective_message.text.strip()
task_ids = context.user_data.get("edit_task_ids", [])  # or "delete_task_ids"
if not text.isdigit() or not task_ids:
    await update.effective_message.reply_text(
        f"Vui lòng nhập số từ 1 đến {len(task_ids)}:"
    )
    return EDIT_SELECT  # re-prompt same state

choice = int(text)
if choice < 1 or choice > len(task_ids):
    await update.effective_message.reply_text(
        f"Số không hợp lệ. Vui lòng nhập số từ 1 đến {len(task_ids)}:"
    )
    return EDIT_SELECT

task_id = task_ids[choice - 1]
conn = context.application.bot_data["db"]
try:
    task = task_repo.get_task_by_id(conn, task_id)
except Exception as exc:
    logger.error("Failed to fetch task: %s", exc)
    await update.effective_message.reply_text("Không thể tải Task. Vui lòng thử lại sau.")
    return ConversationHandler.END

if task is None:
    await update.effective_message.reply_text("Task không còn tồn tại. Vui lòng bắt đầu lại.")
    return ConversationHandler.END

context.user_data["edit_task"] = dict(task)  # convert Row → dict for safe storage
```

**Why `dict(task)` instead of storing the Row directly:** `sqlite3.Row` objects are tied to the cursor lifetime and can become stale. Converting to `dict` at storage time ensures the values are always accessible.

### edit_start Full Pattern

```python
@admin_only
async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    conn = context.application.bot_data["db"]
    try:
        rows = task_repo.get_all_tasks(conn)
    except Exception as exc:
        logger.error("Failed to load tasks for edit: %s", exc)
        await update.effective_message.reply_text("Không thể tải danh sách. Vui lòng thử lại sau.")
        return ConversationHandler.END

    if not rows:
        await update.effective_message.reply_text("Chưa có công việc nào để sửa. Dùng /add để thêm.")
        return ConversationHandler.END

    today = date.today()
    lines = ["📋 Chọn số thứ tự Task muốn sửa:\n"]
    for i, row in enumerate(rows, 1):
        try:
            due_date = date.fromisoformat(row["next_due_date"])
            delta = (due_date - today).days
            if delta < 0:
                status = f"⚠️ Quá hạn {abs(delta)} ngày"
            elif delta == 0:
                status = "📅 Đến hạn hôm nay"
            else:
                status = f"còn {delta} ngày"
            date_display = due_date.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            status = "⚠️ Ngày không hợp lệ"
            date_display = html.escape(str(row["next_due_date"]))
        lines.append(f"{i}. <b>{html.escape(row['name'])}</b> — {date_display} ({status})")
    lines.append("\n(hoặc /cancel để hủy)")

    context.user_data["edit_task_ids"] = [row["id"] for row in rows]
    try:
        await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send edit list: %s", exc)
        await update.effective_message.reply_text("Không thể gửi danh sách. Vui lòng thử lại sau.")
        return ConversationHandler.END
    return EDIT_SELECT
```

### receive_edit_name — "Keep old" Pattern

```python
async def receive_edit_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("edit_task")
    if task is None:
        await update.effective_message.reply_text("Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /edit.")
        return ConversationHandler.END

    if _is_keep_old(text):
        new_name = task["name"]
    else:
        if len(text) > MAX_TASK_NAME_LEN:
            await update.effective_message.reply_text(
                f"Tên quá dài (tối đa {MAX_TASK_NAME_LEN} ký tự). Nhập lại:"
            )
            return EDIT_NAME
        new_name = text

    context.user_data["edit_name"] = new_name
    await update.effective_message.reply_text(
        f"Chu kỳ hiện tại: <b>{task['cycle_days']} ngày</b>.\n"
        f"Nhập chu kỳ mới (hoặc '-' để giữ nguyên):",
        parse_mode="HTML",
    )
    return EDIT_CYCLE
```

### receive_edit_date + save — Exact Pattern

```python
async def receive_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    task = context.user_data.get("edit_task")
    new_name = context.user_data.get("edit_name")
    new_cycle = context.user_data.get("edit_cycle")
    if task is None or new_name is None or new_cycle is None:
        await update.effective_message.reply_text("Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /edit.")
        return ConversationHandler.END

    if _is_keep_old(text):
        new_date_str = task["next_due_date"]
        due_date = date.fromisoformat(new_date_str)
    else:
        try:
            due_date = datetime.strptime(text, "%d/%m/%Y").date()
            new_date_str = due_date.isoformat()
        except ValueError:
            await update.effective_message.reply_text(
                "Ngày không hợp lệ. Vui lòng nhập theo định dạng DD/MM/YYYY (hoặc '-' để giữ nguyên):"
            )
            return EDIT_DATE

    conn = context.application.bot_data["db"]
    try:
        task_repo.update_task(conn, task["id"], new_name, new_cycle, new_date_str)
    except Exception as exc:
        logger.error("Failed to update task: %s", exc)
        await update.effective_message.reply_text("Không thể cập nhật Task. Vui lòng thử lại sau.")
        return ConversationHandler.END

    reminder_date = due_date - timedelta(days=1)
    try:
        await update.effective_message.reply_text(
            f"✅ Đã cập nhật: <b>{html.escape(new_name)}</b> — "
            f"đến hạn {due_date.strftime('%d/%m/%Y')}, "
            f"nhắc trước 1 ngày vào {reminder_date.strftime('%d/%m/%Y')}.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.error("Failed to send update confirmation: %s", exc)
    return ConversationHandler.END
```

### build_edit_conversation — Exact Implementation

```python
def build_edit_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_select)],
            EDIT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_name)],
            EDIT_CYCLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_cycle)],
            EDIT_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edit_date)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
```

### build_delete_conversation — Exact Implementation

```python
def build_delete_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={
            DELETE_SELECT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_select)],
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_confirm)],
        },
        fallbacks=[CommandHandler("cancel", delete_cancel)],
    )
```

### main.py — Exact Change

```python
# Change import line from:
from homekeeper.bot.task_handlers import build_add_conversation, list_handler
# To:
from homekeeper.bot.task_handlers import (
    build_add_conversation,
    build_delete_conversation,
    build_edit_conversation,
    list_handler,
)

# Add handler registrations after build_add_conversation():
application.add_handler(build_edit_conversation())
application.add_handler(build_delete_conversation())
```

### Architecture Constraints

| Rule | Story 1.4 compliance |
|------|--------------------|
| AD-1 Downward-only imports | task_repo only imports `sqlite3` (stdlib) — no bot/ imports ✓ |
| AD-4 No HTTP client | Only Telegram replies — no external calls ✓ |
| AD-5 One conn/thread | All handlers read from `bot_data["db"]` ✓ |
| AD-7 ConversationHandler in-memory state | `context.user_data` is PTB in-memory — never persisted ✓ |
| AD-8 Single writer for TASK.next_due_date | `update_task` is in bot/ layer (not scheduler) — OK; scheduler is read-only on TASK ✓ |
| `@admin_only` on ALL entry-point handlers | `edit_start` and `delete_start` must both be decorated ✓ |

### Story 1.3 Review Learnings (carry forward)

- **Wrap BOTH the DB call AND the final `reply_text` in separate try/except blocks** — the Story 1.3 review found that the original code only wrapped the DB call, leaving Telegram API errors uncaught.
- **`date.fromisoformat()` inside a loop needs try/except (ValueError, TypeError)** — malformed data in any row crashes the whole handler.
- **`dict(task)` when storing `sqlite3.Row` in `context.user_data`** — Row objects are cursor-scoped; convert to dict at storage time.
- **html.escape on ALL user-supplied strings** — task name in ALL HTML messages.
- **Re-prompt on validation error, don't return END** — users should stay in the conversation state.
- **`get_all_tasks` already uses ORDER BY next_due_date ASC, id ASC** — REUSE it for consistent numbering between `/list`, `/edit`, and `/delete`.

### File List for This Story

```
homekeeper/db/task_repo.py         ← UPDATE (add get_task_by_id, update_task, delete_task)
homekeeper/bot/task_handlers.py    ← UPDATE (new states + edit/delete flow + builders)
main.py                            ← UPDATE (import + register edit + delete conversations)
tests/test_task_repo_crud.py       ← NEW (tests for get_task_by_id, update_task, delete_task)
tests/test_edit_handler.py         ← NEW (tests for edit conversation)
tests/test_delete_handler.py       ← NEW (tests for delete conversation)
```

### References

- [Source: planning-artifacts/epics.md — Story 1.4 Acceptance Criteria]
- [Source: planning-artifacts/architecture/ARCHITECTURE-SPINE.md — AD-1, AD-5, AD-7, AD-8]
- [Source: implementation-artifacts/1-3-view-task-list.md — Story 1.3 patterns, review learnings]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- No dependency issues; python-telegram-bot already installed from Story 1.3

### Completion Notes List

- Implemented `get_task_by_id`, `update_task`, `delete_task` in task_repo.py (all stdlib-only, AD-1 compliant)
- Added state constants EDIT_SELECT/EDIT_NAME/EDIT_CYCLE/EDIT_DATE (3–6) and DELETE_SELECT/DELETE_CONFIRM (7–8); no overlap with add states (0–2)
- Added `_is_keep_old(text)` helper — returns True for blank/"-" input
- Implemented full edit conversation: `edit_start`, `receive_edit_select`, `receive_edit_name`, `receive_edit_cycle`, `receive_edit_date`, `edit_cancel`, `build_edit_conversation()`
- Implemented full delete conversation: `delete_start`, `receive_delete_select`, `receive_delete_confirm`, `delete_cancel`, `build_delete_conversation()`
- All entry-point handlers decorated with `@admin_only` (edit_start, delete_start)
- `dict(task)` used when storing sqlite3.Row in context.user_data (Row cursor-scoping, learned from Story 1.3)
- Both DB calls and final reply_text wrapped in separate try/except blocks (learned from Story 1.3 review)
- per-row `date.fromisoformat()` wrapped in try/except (ValueError, TypeError) in both list displays
- html.escape applied to all user-supplied strings in HTML messages
- Wired build_edit_conversation() and build_delete_conversation() into main.py
- 58 tests total, 0 failures: 9 DB tests, 21 edit handler tests, 14 delete handler tests, 14 Story 1.3 regression tests

### File List

- homekeeper/db/task_repo.py (updated — added get_task_by_id, update_task, delete_task)
- homekeeper/bot/task_handlers.py (updated — added EDIT_*/DELETE_* states, _is_keep_old, edit+delete handlers and builders)
- main.py (updated — imported build_edit_conversation, build_delete_conversation; registered handlers)
- tests/test_task_repo_crud.py (new — 9 tests for get_task_by_id, update_task, delete_task)
- tests/test_edit_handler.py (new — 21 tests for edit conversation)
- tests/test_delete_handler.py (new — 14 tests for delete conversation)

### Review Findings

- [x] [Review][Patch] `receive_edit_cycle` missing None-guard on `task` before accessing `task["cycle_days"]` [homekeeper/bot/task_handlers.py:receive_edit_cycle] — unlike `receive_edit_name` and `receive_edit_date`, this handler does not check `if task is None` before the `_is_keep_old` branch, causing `TypeError: 'NoneType' object is not subscriptable` on session loss or bot restart mid-conversation
- [x] [Review][Patch] `receive_edit_date` keep-old branch: `date.fromisoformat(new_date_str)` unguarded [homekeeper/bot/task_handlers.py:receive_edit_date:340] — when user sends blank/"-" to keep old date, `new_date_str = task["next_due_date"]` and the subsequent `date.fromisoformat()` call has no `try/except (ValueError, TypeError)`; if the stored date is malformed, this propagates as an unhandled exception
- [x] [Review][Patch] `receive_edit_cycle` displays `next_due_date` in raw ISO format `YYYY-MM-DD` [homekeeper/bot/task_handlers.py:receive_edit_cycle:320] — the prompt `f"Ngày đến hạn hiện tại: <b>{task['next_due_date']}</b>"` shows the ISO string (e.g. `2026-06-29`) instead of `DD/MM/YYYY` format used everywhere else in the UI
- [x] [Review][Defer] `update_task`/`delete_task` silent no-op when `task_id` doesn't exist — `cursor.rowcount` is never checked; if task deleted between list display and confirm, success message is shown for a no-op UPDATE/DELETE [homekeeper/db/task_repo.py] — deferred, TOCTOU race extremely low probability on single-admin personal bot
- [x] [Review][Defer] TOCTOU: task list index snapshot can diverge from DB state during multi-step edit/delete flow [homekeeper/bot/task_handlers.py:edit_start,delete_start] — deferred, architectural limitation of ConversationHandler pattern; re-fetch by id already mitigates the worst case
- [x] [Review][Defer] 30+ lines of task list rendering logic copy-pasted between `edit_start` and `delete_start` [homekeeper/bot/task_handlers.py:204-228,411-438] — deferred, refactoring suggestion, no functional impact
- [x] [Review][Defer] `receive_edit_date` accepts any date without sanity bounds (past dates, year 9999) [homekeeper/bot/task_handlers.py:receive_edit_date] — deferred, spec does not require date bounds
- [x] [Review][Defer] Confirmation message hard-codes "reminder = due_date − 1 day" display regardless of actual scheduler config [homekeeper/bot/task_handlers.py:receive_edit_date:362-370] — deferred, Story 2.1 owns reminder logic; display is informational only
- [x] [Review][Defer] `receive_edit_cycle`: very large cycle values (e.g. `9999999`) accepted without upper bound [homekeeper/bot/task_handlers.py:receive_edit_cycle] — deferred, personal bot; cosmetic issue only
- [x] [Review][Defer] `allow_reentry=True` not set on `build_edit_conversation` / `build_delete_conversation` [homekeeper/bot/task_handlers.py:380-390,524-532] — deferred, PTB default silently ignores `/edit` re-entry; acceptable for single-admin bot
- [x] [Review][Defer] `context.user_data` accumulates stale keys after conversation END [homekeeper/bot/task_handlers.py] — deferred, pre-existing pattern from Story 1.2; no functional risk for single-user bot
- [x] [Review][Defer] "1 đến 0" error message possible when `task_ids` is empty in select handlers [homekeeper/bot/task_handlers.py:receive_edit_select,receive_delete_select] — deferred, requires prior session corruption to trigger; negligible
