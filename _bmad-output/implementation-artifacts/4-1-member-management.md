---
status: done
baseline_commit: NO_VCS
---

# Story 4.1: Member Management

Status: done

## Story

As an Admin,
I want to add and remove family members by their Telegram user ID,
So that they receive the same reminders and can report incidents without needing separate setup.

## Acceptance Criteria

**AC-1 — Add member flow:**
**Given** Admin gửi `/member add`
**When** Bot nhận lệnh
**Then** Bot hỏi: "Nhập Telegram user ID của thành viên: (họ cần nhắn tin cho bot trước để lấy ID)"

**AC-2 — Save member after valid ID + name:**
**Given** Admin nhập một Telegram user ID hợp lệ (số nguyên dương)
**When** Bot validate
**Then** Bot hỏi tên hiển thị của Member
**And** Sau khi Admin nhập tên, Bot lưu Member vào bảng MEMBER với `telegram_user_id` và `name`
**And** Bot xác nhận: "✅ Đã thêm thành viên: **[tên]** (ID: [telegram_user_id])."

**AC-3 — Duplicate telegram_user_id:**
**Given** Admin nhập một Telegram user ID đã tồn tại trong bảng MEMBER
**When** Bot kiểm tra DB
**Then** Bot báo: "Thành viên này đã có trong danh sách." và không tạo bản ghi trùng

**AC-4 — List members:**
**Given** Admin gửi `/member list`
**When** Có Member trong database
**Then** Bot trả về danh sách tất cả Member với tên và Telegram user ID

**Given** Admin gửi `/member list`
**When** Không có Member nào
**Then** Bot trả về: "Chưa có thành viên nào. Dùng /member add để thêm."

**AC-5 — Remove member:**
**Given** Admin gửi `/member remove` và chọn một Member
**When** Admin xác nhận "Có"
**Then** Member bị xóa khỏi bảng MEMBER và không còn nhận Reminder
**And** Bot xác nhận: "✅ Đã xóa thành viên: **[tên]**."

**AC-6 — Admin-only access:**
**Given** Một Telegram user không phải Admin gửi bất kỳ lệnh `/member` nào
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền quản lý thành viên." (FR-12)

## Tasks / Subtasks

- [x] Task 1: Extend `homekeeper/db/member_repo.py` with add/lookup/delete functions + write `tests/test_member_repo.py` (AC: 2, 3, 4, 5)
  - [x] 1.1 Add `get_member_by_telegram_id(conn, telegram_user_id: int)` — `SELECT id, telegram_user_id, name FROM MEMBER WHERE telegram_user_id = ?`; return `cursor.fetchone()` (None if not found)
  - [x] 1.2 Add `add_member(conn, telegram_user_id: int, name: str) -> None` — `INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)`; let `sqlite3.IntegrityError` propagate on UNIQUE violation (caller must pre-check or catch)
  - [x] 1.3 Add `delete_member(conn, member_id: int) -> None` — `DELETE FROM MEMBER WHERE id = ?`; no-op if ID not found (DELETE of missing row does not raise)
  - [x] 1.4 Viết `tests/test_member_repo.py` (NEW file): add_member persists row, get_member_by_telegram_id returns correct row, get_member_by_telegram_id returns None for missing, second add with same telegram_user_id raises IntegrityError, delete_member removes row, delete_member with nonexistent id does not raise, get_all_members returns all rows in insertion order

- [x] Task 2: Create `homekeeper/bot/member_handlers.py` + write `tests/test_member_handlers.py` (AC: 1–6)
  - [x] 2.1 Define states: `ASK_ADD_ID, ASK_ADD_NAME, REMOVE_SELECT, REMOVE_CONFIRM = range(4)`
  - [x] 2.2 Implement `member_cmd(update, context) -> int` — admin-only auth check (same pattern as `repairman_cmd`), dispatch on `context.args[0]` (`add`, `list`, `remove`); unknown subcommand → reply usage string → END
  - [x] 2.3 Implement `receive_add_id(update, context) -> int` — validate input is positive integer (try/except ValueError + check > 0); call `member_repo.get_member_by_telegram_id` to detect duplicate (AC-3); store valid ID in `context.user_data["add_telegram_id"]`; ask name
  - [x] 2.4 Implement `receive_add_name(update, context) -> int` — require non-empty name; call `member_repo.add_member`; confirm "✅ Đã thêm thành viên: **[tên]** (ID: [id])." with HTML; return END
  - [x] 2.5 Implement `_list_members(update, context) -> int` — load from `member_repo.get_all_members`; format list (see format spec in Dev Notes); return END
  - [x] 2.6 Implement `_start_remove(update, context) -> int` — load members; if empty show "Chưa có thành viên nào."; store IDs in `context.user_data["remove_member_ids"]`; display numbered list; return REMOVE_SELECT
  - [x] 2.7 Implement `receive_remove_select(update, context) -> int` — validate number in range; load member row; store `{"id": ..., "name": ..., "telegram_user_id": ...}` in context.user_data["remove_member"]; ask confirmation text "Bạn có chắc muốn xóa thành viên **[tên]**? Trả lời 'Có' để xác nhận hoặc 'Không' để hủy."; return REMOVE_CONFIRM
  - [x] 2.8 Implement `receive_remove_confirm(update, context) -> int` — if `text.lower() == "có"`: call `member_repo.delete_member`; confirm "✅ Đã xóa thành viên: **[tên]**."; else: reply "Đã hủy xóa."; return END
  - [x] 2.9 Implement `member_cancel(update, context) -> int` — reply "Đã hủy.", return END
  - [x] 2.10 Implement `build_member_conversation() -> ConversationHandler` — entry_points `[CommandHandler("member", member_cmd)]`; states: `{ASK_ADD_ID: [TEXT], ASK_ADD_NAME: [TEXT], REMOVE_SELECT: [TEXT], REMOVE_CONFIRM: [TEXT]}`; fallbacks `[CommandHandler("cancel", member_cancel)]`
  - [x] 2.11 Viết `tests/test_member_handlers.py` (NEW file) — see tests list in Dev Notes

### Review Findings

- [x] [Review][Patch] `receive_remove_select` double-query crash: inner `fetchone()` returns `None` when member deleted between list display and selection → `TypeError` silently swallowed, `row is None` guard is dead code, inline SQL bypasses `member_repo` — fix: add `get_member_by_id` to `member_repo.py` and use it directly (as `repairman_handlers` uses `get_repairman_by_id`) [homekeeper/bot/member_handlers.py:194] (sources: blind+edge+auditor)
- [x] [Review][Patch] `receive_remove_select` uses `text.isdigit()` which returns `True` for Unicode digit characters (e.g. `"²"`), then `int(text)` raises uncaught `ValueError` — fix: wrap `int(text)` in try/except consistent with `receive_add_id` [homekeeper/bot/member_handlers.py:178] (sources: blind+edge)
- [x] [Review][Patch] No test for deleted-member TOCTOU scenario: member removed between list display and selection — add test for `receive_remove_select` where the member_id is no longer in DB [tests/test_member_handlers.py] (source: edge)
- [x] [Review][Defer] `delete_member` silent no-op when row already gone — false "✅ deleted" confirmation — deferred, consistent with `repairman_repo.delete_repairman` pattern [homekeeper/db/member_repo.py:25]
- [x] [Review][Defer] TOCTOU in add flow: pre-check passes but `IntegrityError` in INSERT gives generic message — deferred, single-admin home bot, extremely low probability
- [x] [Review][Defer] `ADMIN_USER_ID=0` no log warning when env var unset — deferred, pre-existing systemic pattern across all handlers
- [x] [Review][Defer] `user_data` keys not cleared on cancel/end — deferred, pre-existing systemic pattern in `repairman_handlers`
- [x] [Review][Defer] `effective_message` None guard missing in state handler functions — deferred, pre-existing systemic pattern in `repairman_handlers`

- [x] Task 3: Wire `main.py` + full suite (AC: all)
  - [x] 3.1 Add `from homekeeper.bot.member_handlers import build_member_conversation` to imports in `main.py`
  - [x] 3.2 Add `application.add_handler(build_member_conversation())` after `build_repairman_conversation()` line
  - [x] 3.3 Run full test suite — tất cả tests GREEN, không regression

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

- **AD-1**: `member_handlers.py` imports from `db/` only (`member_repo`). Never imports from `scheduler/`. `member_repo.py` never imports from `bot/`.
- **AD-5**: All DB access via `context.application.bot_data["db"]` — never create a new connection inside a handler.
- **AD-7**: Conversation state (selected member ID, collected user input) lives in `context.user_data` only — never write conversation state to SQLite.
- **FR-12 / Admin-only**: `/member` commands are admin-only. Use `ADMIN_USER_ID` env var check, NOT `_is_authenticated` (which allows both admin and members — would let a member manage the member list).

### Auth Pattern — Admin-only (copy from `repairman_cmd`)

```python
async def member_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END
    try:
        admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
    except ValueError:
        return ConversationHandler.END
    if update.effective_user.id != admin_id:
        await update.effective_message.reply_text("Bạn không có quyền quản lý thành viên.")
        return ConversationHandler.END
    ...
```

This pattern is identical to `repairman_cmd`. Do NOT use `_is_authenticated` here — that function allows members to pass, which is correct for `/incident` but wrong for `/member`.

### `member_repo.py` — Exact Function Signatures

Current content (do NOT remove `get_all_members`):
```python
def get_all_members(conn: sqlite3.Connection) -> list:
    cursor = conn.execute("SELECT id, telegram_user_id, name FROM MEMBER ORDER BY id ASC")
    return cursor.fetchall()
```

Add these three functions:

```python
def get_member_by_telegram_id(conn: sqlite3.Connection, telegram_user_id: int):
    cursor = conn.execute(
        "SELECT id, telegram_user_id, name FROM MEMBER WHERE telegram_user_id = ?",
        (telegram_user_id,),
    )
    return cursor.fetchone()


def add_member(conn: sqlite3.Connection, telegram_user_id: int, name: str) -> None:
    conn.execute(
        "INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)",
        (telegram_user_id, name),
    )
    conn.commit()


def delete_member(conn: sqlite3.Connection, member_id: int) -> None:
    conn.execute("DELETE FROM MEMBER WHERE id = ?", (member_id,))
    conn.commit()
```

Key notes:
- `add_member` lets `sqlite3.IntegrityError` propagate — but the handler pre-checks with `get_member_by_telegram_id` so the error path is defensive only
- `delete_member` is safe to call with a nonexistent id — SQLite DELETE of zero rows is not an error
- All three functions call `conn.commit()` directly (WAL mode, single PTB thread)

### MEMBER Table Schema (from `schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS MEMBER (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL UNIQUE,
    name             TEXT    -- nullable at schema level, required at app level
);
```

`get_all_members` is already called by `_is_authenticated` in `incident_handlers.py` — the existing function signature and query must not change.

### Telegram User ID Validation in `receive_add_id`

Telegram user IDs are always positive integers. Validate:

```python
async def receive_add_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.effective_message.text.strip()
    try:
        telegram_user_id = int(text)
    except ValueError:
        await update.effective_message.reply_text(
            "ID không hợp lệ. Vui lòng nhập một số nguyên (ví dụ: 123456789):"
        )
        return ASK_ADD_ID
    if telegram_user_id <= 0:
        await update.effective_message.reply_text(
            "ID phải là số nguyên dương. Nhập lại:"
        )
        return ASK_ADD_ID

    conn = context.application.bot_data["db"]
    existing = member_repo.get_member_by_telegram_id(conn, telegram_user_id)
    if existing is not None:
        await update.effective_message.reply_text("Thành viên này đã có trong danh sách.")
        return ConversationHandler.END

    context.user_data["add_telegram_id"] = telegram_user_id
    await update.effective_message.reply_text("Nhập tên của thành viên:")
    return ASK_ADD_NAME
```

### `receive_add_name` — Save and Confirm

```python
async def receive_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.effective_message.text.strip()
    if not name:
        await update.effective_message.reply_text("Tên không được để trống. Nhập lại:")
        return ASK_ADD_NAME

    telegram_user_id = context.user_data.get("add_telegram_id")
    if telegram_user_id is None:
        await update.effective_message.reply_text(
            "Đã xảy ra lỗi. Vui lòng bắt đầu lại bằng /member add."
        )
        return ConversationHandler.END

    conn = context.application.bot_data["db"]
    try:
        member_repo.add_member(conn, telegram_user_id, name)
    except Exception as exc:
        logger.error("Failed to save member: %s", exc)
        await update.effective_message.reply_text(
            "Không thể lưu thành viên. Vui lòng thử lại."
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        f"✅ Đã thêm thành viên: <b>{html.escape(name)}</b> (ID: {telegram_user_id}).",
        parse_mode="HTML",
    )
    return ConversationHandler.END
```

### List Format

Follow repairman list pattern — HTML formatted, numbered:

```python
async def _list_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    conn = context.application.bot_data["db"]
    try:
        rows = member_repo.get_all_members(conn)
    except Exception as exc:
        logger.error("Failed to load members: %s", exc)
        await update.effective_message.reply_text(
            "Không thể tải danh sách thành viên. Vui lòng thử lại sau."
        )
        return ConversationHandler.END
    if not rows:
        await update.effective_message.reply_text(
            "Chưa có thành viên nào. Dùng /member add để thêm."
        )
        return ConversationHandler.END

    lines = [f"👥 <b>Danh sách thành viên</b> ({len(rows)} người):\n"]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. <b>{html.escape(row['name'] or '(không tên)')}</b> — ID: {row['telegram_user_id']}"
        )
    await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    return ConversationHandler.END
```

### Remove Flow — Same Pattern as Repairman Delete

`_start_remove` shows numbered list and stores IDs in `context.user_data["remove_member_ids"]`.
`receive_remove_select` validates number, loads row, stores `{"id": ..., "name": ..., "telegram_user_id": ...}` in `context.user_data["remove_member"]`.
`receive_remove_confirm` checks `text.lower() == "có"` → delete; else → cancel.

Confirmation prompt (in `receive_remove_select`):
```python
await update.effective_message.reply_text(
    f"Bạn có chắc muốn xóa thành viên <b>{html.escape(row['name'] or '(không tên)')}</b>? "
    f"Trả lời 'Có' để xác nhận hoặc 'Không' để hủy.",
    parse_mode="HTML",
)
```

Delete confirmation (in `receive_remove_confirm`):
```python
await update.effective_message.reply_text(
    f"✅ Đã xóa thành viên: <b>{html.escape(member['name'] or '(không tên)')}</b>.",
    parse_mode="HTML",
)
```

### `build_member_conversation()` — Exact Builder Structure

```python
def build_member_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("member", member_cmd)],
        states={
            ASK_ADD_ID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_id)],
            ASK_ADD_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_name)],
            REMOVE_SELECT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remove_select)],
            REMOVE_CONFIRM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_remove_confirm)],
        },
        fallbacks=[CommandHandler("cancel", member_cancel)],
    )
```

### Required Imports for `member_handlers.py`

```python
import html
import logging
import os

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from homekeeper.db import member_repo
```

### `main.py` — Single Change

Add one import and one `add_handler` call. The handler must be registered before the global `CallbackQueryHandler` entries (consistent with existing pattern — all ConversationHandlers first):

```python
# import block — add alongside build_repairman_conversation:
from homekeeper.bot.member_handlers import build_member_conversation

# in main(), after build_repairman_conversation():
application.add_handler(build_member_conversation())
```

### `tests/test_member_repo.py` — Required Tests

New file. Use same `conn` fixture pattern as existing tests (`:memory:` + schema.sql).

Tests to write:
1. `test_add_member_persists_row` — add then get_all_members returns 1 row with correct fields
2. `test_add_member_returns_none_not_raises` — `add_member` returns None; no exception
3. `test_add_member_duplicate_raises_integrity_error` — second add with same telegram_user_id raises `sqlite3.IntegrityError`
4. `test_get_member_by_telegram_id_returns_correct_row` — correct `telegram_user_id` and `name`
5. `test_get_member_by_telegram_id_returns_none_for_missing` — returns None for unknown id
6. `test_delete_member_removes_row` — row gone from get_all_members after delete
7. `test_delete_member_nonexistent_no_error` — delete with nonexistent id does not raise
8. `test_get_all_members_returns_in_insertion_order` — two members returned in id-ascending order

### `tests/test_member_handlers.py` — Required Tests

New file. Test structure (follow `tests/test_repairman_handlers.py` and `tests/test_incident_handlers.py` patterns for fixtures and `_make_uc`):

**Auth tests:**
- `test_unauthenticated_user_rejected` — non-admin gets "Bạn không có quyền quản lý thành viên."
- `test_admin_can_access_add` — admin gets ASK_ADD_ID state
- `test_effective_user_none_returns_end` — returns END, no crash

**Add flow:**
- `test_add_invalid_id_rejected` — "abc" returns ASK_ADD_ID
- `test_add_zero_id_rejected` — "0" returns ASK_ADD_ID
- `test_add_negative_id_rejected` — "-1" returns ASK_ADD_ID
- `test_add_valid_id_asks_name` — "123456" returns ASK_ADD_NAME, stores id in context.user_data
- `test_add_duplicate_id_shows_message` — id already in DB → "Thành viên này đã có"
- `test_add_empty_name_rejected` — "   " returns ASK_ADD_NAME
- `test_add_valid_name_saves_and_confirms` — member in DB, reply contains name and ID
- `test_add_confirmation_uses_html` — reply_text called with parse_mode="HTML"

**List:**
- `test_list_empty_db` — reply contains "Chưa có thành viên nào"
- `test_list_shows_all_members` — two members → both in reply text
- `test_list_shows_telegram_user_id` — ID visible in output

**Remove flow:**
- `test_remove_empty_db` — reply contains "Chưa có thành viên nào"
- `test_remove_select_shows_numbered_list` — member name in reply text
- `test_remove_select_invalid_number_rejected` — "99" (out of range) returns REMOVE_SELECT
- `test_remove_confirm_co_deletes_member` — row gone from DB after "Có"
- `test_remove_confirm_khong_cancels` — row still in DB after "Không"

**Builder:**
- `test_build_member_conversation_returns_handler` — isinstance check

### Files in This Story

| File | Action |
|------|--------|
| `homekeeper/db/member_repo.py` | UPDATE — add `get_member_by_telegram_id`, `add_member`, `delete_member` |
| `homekeeper/bot/member_handlers.py` | NEW — full ConversationHandler for add/list/remove |
| `main.py` | UPDATE — import + register `build_member_conversation` |
| `tests/test_member_repo.py` | NEW |
| `tests/test_member_handlers.py` | NEW |

**DO NOT modify**: `schema.sql` (MEMBER table already correct), any existing handler, `homekeeper/db/connection.py`, `homekeeper/domain/`.

### Previous Story Learnings (from Stories 3.1–3.3)

1. **`get_all_members` already exists** — must not remove or duplicate it. Only add new functions below it.
2. **`html.escape()` required** for all user-input fields in HTML-formatted replies (`parse_mode="HTML"`). Member `name` comes from user input → must be escaped.
3. **`name` may be None from DB** — the schema column has no NOT NULL constraint. Guard with `row['name'] or '(không tên)'` in display code to avoid crashing on old/NULL rows (defensive only — new inserts always have non-empty name).
4. **`context.user_data` for state** — store collected inputs (telegram_user_id, selected member) between conversation steps. Never persist conversation state to SQLite (AD-7).
5. **Delete confirmation is text-based** — "Có"/"Không" as free text (same as `repairman_handlers.py:359`). No inline keyboard in the delete flow.
6. **Repo test helpers**: seed directly via `member_repo.add_member(conn, ...)` in test helpers — never bypass the repo with raw SQL (lesson from Story 3.3 code review P3).
7. **Error handling in ConversationHandler state functions**: always return a valid state (not raise). Return `ConversationHandler.END` on unrecoverable errors, return the current state (e.g., `ASK_ADD_ID`) to let user retry.
8. **Full test suite baseline**: 261 tests after Story 3.3. This story should add ~20 tests → expect ~281 passing at end. Any regression = STOP and fix before completing Task 3.

### References

- `homekeeper/bot/repairman_handlers.py` — exact template for ConversationHandler structure, admin auth, HTML output, delete flow
- `homekeeper/db/member_repo.py` — existing `get_all_members` (do not touch)
- `homekeeper/db/schema.sql` — MEMBER table (no schema change needed)
- `main.py` — registration order for `add_handler` calls
- `_bmad-output/planning-artifacts/epics.md` — Story 4.1 section for AC source text
- `_bmad-output/planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md` — AD-1, AD-5, AD-7, CAP-5

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1: Added `get_member_by_telegram_id`, `add_member`, `delete_member` to `member_repo.py`. Updated `test_member_repo.py` with 8 new tests (11 total). All 11 GREEN, 292/292 full suite.
- Task 2: Created `member_handlers.py` — ConversationHandler with add (2-step: ID + name), list, remove (select + confirm) flows; admin-only auth via `ADMIN_USER_ID`; `html.escape()` + `parse_mode="HTML"`. Created `tests/test_member_handlers.py` with 23 tests. All 23 GREEN.
- Task 3: Wired `main.py` — added import and `add_handler(build_member_conversation())` after `build_repairman_conversation()`. Full suite: **292/292 passed**, zero regressions.

### File List

- `homekeeper/db/member_repo.py` (UPDATED — added `get_member_by_telegram_id`, `add_member`, `delete_member`)
- `homekeeper/bot/member_handlers.py` (NEW)
- `main.py` (UPDATED — import + handler registration)
- `tests/test_member_repo.py` (UPDATED — 8 new tests added)
- `tests/test_member_handlers.py` (NEW — 23 tests)
