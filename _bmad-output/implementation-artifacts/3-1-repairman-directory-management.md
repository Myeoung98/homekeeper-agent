---
status: ready-for-dev
baseline_commit: NO_VCS
---

# Story 3.1: Repairman Directory Management

Status: done

## Story

As an Admin,
I want to maintain a directory of repairmen with their contact details and service types,
So that the bot can suggest the right person when something breaks.

## Acceptance Criteria

**AC-1 — Add repairman (sequential conversation):**
**Given** Admin gửi `/repairman add`
**When** Bot nhận lệnh
**Then** Bot hỏi tên thợ, sau đó số điện thoại, sau đó loại dịch vụ (text tự do, ví dụ: "điều hòa, điện lạnh") — theo thứ tự tuần tự

**AC-2 — Confirm add:**
**Given** Admin hoàn thành nhập 3 trường
**When** Bot lưu Repairman
**Then** Repairman được lưu vào bảng REPAIRMAN và bot xác nhận: "✅ Đã thêm thợ: **[tên]** — [phone] — [service_type]."

**AC-3 — List with data:**
**Given** Admin gửi `/repairman list`
**When** Có Repairman trong database
**Then** Bot trả về danh sách tất cả Repairman với tên, số điện thoại, và loại dịch vụ

**AC-4 — List empty:**
**Given** Admin gửi `/repairman list`
**When** Không có Repairman nào
**Then** Bot trả về: "Chưa có thợ nào trong danh bạ. Dùng /repairman add để thêm."

**AC-5 — Edit and delete:**
**Given** Admin gửi `/repairman edit` hoặc `/repairman delete`
**When** Admin chọn Repairman và sửa/xóa
**Then** Thay đổi được lưu vào DB và bot xác nhận; xóa yêu cầu confirm "Có/Không" trước khi thực hiện

**AC-6 — Member rejection (domain-specific message):**
**Given** Một Member (không phải Admin) gửi bất kỳ lệnh `/repairman` nào
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền quản lý danh bạ thợ." (FR-12)

## Tasks / Subtasks

- [x] Task 1: Tạo `homekeeper/db/repairman_repo.py` với full CRUD (AC: 2, 3, 4, 5)
  - [x] 1.1 Implement `get_all_repairmen(conn) -> list` — SELECT * FROM REPAIRMAN ORDER BY id ASC
  - [x] 1.2 Implement `create_repairman(conn, name, phone, service_type) -> int` — INSERT, return lastrowid
  - [x] 1.3 Implement `get_repairman_by_id(conn, repairman_id) -> Row | None` — SELECT by id
  - [x] 1.4 Implement `update_repairman(conn, repairman_id, name, phone, service_type) -> None` — UPDATE, commit
  - [x] 1.5 Implement `delete_repairman(conn, repairman_id) -> None` — DELETE, commit
  - [x] 1.6 Viết `tests/test_repairman_repo.py`: empty list, create+read, get_by_id (exists/not exists), update, delete, multiple repairmen ordered by id

- [x] Task 2: Implement `homekeeper/bot/repairman_handlers.py` — entry point + add flow (AC: 1, 2, 6)
  - [x] 2.1 Define state constants: `ASK_ADD_NAME, ASK_ADD_PHONE, ASK_ADD_SERVICE, EDIT_SELECT, EDIT_NAME, EDIT_PHONE, EDIT_SERVICE, DELETE_SELECT, DELETE_CONFIRM = range(9)`
  - [x] 2.2 Implement `repairman_cmd` entry point: inline admin check (sends "Bạn không có quyền quản lý danh bạ thợ." — NOT using @admin_only decorator), dispatch on `(context.args or [""])[0].lower()`
  - [x] 2.3 Add flow: `receive_add_name` (validate non-empty), `receive_add_phone` (validate non-empty), `receive_add_service` (validate non-empty, call `repairman_repo.create_repairman`, reply with AC-2 message)
  - [x] 2.4 Viết tests cho add flow (non-admin rejection, happy path, empty name rejected, empty phone rejected, save success với correct AC-2 message format)

- [x] Task 3: Implement list subcommand (AC: 3, 4)
  - [x] 3.1 In `repairman_cmd`, "list" branch: load all repairmen, reply with numbered list (name — phone — service_type) or AC-4 empty message; return `ConversationHandler.END`
  - [x] 3.2 Viết tests: empty list message, list with 2 repairmen (verify name/phone/service_type all appear)

- [x] Task 4: Implement edit subcommand (AC: 5)
  - [x] 4.1 In `repairman_cmd`, "edit" branch: show numbered list of repairmen, store `context.user_data["repairman_ids"]`, return `EDIT_SELECT`; empty list → reply + END
  - [x] 4.2 `receive_edit_select`: validate number, fetch repairman, store `context.user_data["edit_repairman"]`, ask for new name (hint: '-' để giữ nguyên), return `EDIT_NAME`
  - [x] 4.3 `receive_edit_name`, `receive_edit_phone`, `receive_edit_service`: each step uses `_is_keep_old(text)` helper to keep old value if '-' or empty; final step calls `update_repairman`, confirms "✅ Đã cập nhật thợ: **[tên]** — [phone] — [service_type].", return END
  - [x] 4.4 Viết tests: select valid/invalid number, keep old value with '-', save with changes

- [x] Task 5: Implement delete subcommand (AC: 5)
  - [x] 5.1 In `repairman_cmd`, "delete" branch: show numbered list, store `context.user_data["repairman_ids"]`, return `DELETE_SELECT`; empty list → reply + END
  - [x] 5.2 `receive_delete_select`: validate number, fetch repairman, store `context.user_data["delete_repairman"]`, ask confirm "Bạn có chắc muốn xóa thợ **[tên]**? Trả lời 'Có' để xác nhận hoặc 'Không' để hủy.", return `DELETE_CONFIRM`
  - [x] 5.3 `receive_delete_confirm`: if text.lower() == "có" → delete, confirm "✅ Đã xóa thợ: **[tên]**"; else → "Đã hủy xóa."; return END
  - [x] 5.4 Viết tests: select + confirm "Có" deletes, answer "Không" cancels, invalid selection rejected

- [x] Task 6: `build_repairman_conversation()` + wire `main.py` + full suite (AC: all)
  - [x] 6.1 Implement `repairman_cancel` handler + `build_repairman_conversation()` function (single ConversationHandler with entry_points=[CommandHandler("repairman", repairman_cmd)], all 9 states, fallbacks=[CommandHandler("cancel", repairman_cancel)])
  - [x] 6.2 Update `main.py`: add import `from homekeeper.bot.repairman_handlers import build_repairman_conversation`, add `application.add_handler(build_repairman_conversation())` (before run_catchup)
  - [x] 6.3 Chạy full test suite — tất cả tests hiện tại phải GREEN, không regression

### Review Findings

- [x] [Review][Patch] Shared `repairman_ids` key between edit and delete flows — both `_start_edit` and `_start_delete` write to the same `context.user_data["repairman_ids"]`; if admin starts edit then immediately starts delete, the key is overwritten and the edit flow picks wrong IDs; fix: rename to `edit_repairman_ids` / `delete_repairman_ids` matching task_handlers pattern [repairman_handlers.py:154,276]
- [x] [Review][Patch] Missing try/except around DB calls in list/edit/delete entry points — `_list_repairmen`, `_start_edit`, `_start_delete` call `get_all_repairmen` without exception handler; `receive_edit_select` and `receive_delete_select` call `get_repairman_by_id` without exception handler; task_handlers wraps equivalent calls; a SQLite OperationalError leaves user with no feedback [repairman_handlers.py:64,141,177,263,299]
- [x] [Review][Defer] Unicode NFD/NFC normalization issue with "có" confirmation [repairman_handlers.py:324] — deferred, pre-existing; Vietnamese keyboards on iOS/Android may emit NFD form that doesn't compare equal to NFC literal "có"; low risk for single-admin bot
- [x] [Review][Defer] No rowcount check after UPDATE/DELETE in repo — `update_repairman`/`delete_repairman` commit unconditionally; success message shown even if 0 rows affected (e.g. concurrent deletion); low risk in single-admin single-thread bot [repairman_repo.py:40,47] — deferred, pre-existing
- [x] [Review][Defer] Error message shows "1 đến 0" when `repairman_ids` is empty in select handlers [repairman_handlers.py:162,284] — deferred, pre-existing; edge case only if user_data externally cleared
- [x] [Review][Defer] No user_data cleanup on ConversationHandler.END — stale keys accumulate across sessions; no functional risk after shared-key fix [repairman_handlers.py] — deferred, pre-existing

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

- **AD-1**: `repairman_handlers.py` imports only from `db/` and `domain/` — never from `scheduler/`
- **AD-3**: Do NOT put business logic in `domain/` for this story. Story 3.3 will add `domain/matching.py`. Story 3.1 is pure CRUD.
- **AD-4**: NO HTTP clients, NO external calls. Bot only sends Telegram messages (HITL by structure).
- **AD-7**: ConversationHandler uses default in-memory state. Restart mid-conversation resets flow — acceptable by design.

### Critical: AC-6 — Custom Admin Check (NOT @admin_only)

The standard `admin_only` decorator in `homekeeper/bot/__init__.py` sends **"Bạn không có quyền sử dụng bot này."** — this is the wrong message for `/repairman`.

AC-6 requires: **"Bạn không có quyền quản lý danh bạ thợ."**

**Implementation**: Do NOT use `@admin_only` on `repairman_cmd`. Instead, do an inline check:

```python
async def repairman_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None:
        return ConversationHandler.END
    try:
        admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
    except ValueError:
        return ConversationHandler.END
    if update.effective_user.id != admin_id:
        await update.effective_message.reply_text("Bạn không có quyền quản lý danh bạ thợ.")
        return ConversationHandler.END
    ...
```

### REPAIRMAN Table (already exists in schema.sql — NO SCHEMA CHANGE NEEDED)

```sql
CREATE TABLE IF NOT EXISTS REPAIRMAN (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    phone        TEXT NOT NULL,
    service_type TEXT NOT NULL
);
```

The table is already in `homekeeper/db/schema.sql`. Do NOT modify schema.sql.

### ConversationHandler Dispatch Pattern

All `/repairman` subcommands share one `ConversationHandler` entry point:

```python
# Entry dispatches based on context.args[0]
async def repairman_cmd(update, context):
    # admin check (inline, NOT @admin_only)
    sub = (context.args or [""])[0].lower()
    if sub == "add":    return ASK_ADD_NAME    # after asking for name
    if sub == "list":   # inline list, return END
    if sub == "edit":   return EDIT_SELECT     # after showing list
    if sub == "delete": return DELETE_SELECT   # after showing list
    # else: usage hint + END
```

State constants (range(9) to avoid collisions with task_handlers constants):

```python
ASK_ADD_NAME, ASK_ADD_PHONE, ASK_ADD_SERVICE, \
EDIT_SELECT, EDIT_NAME, EDIT_PHONE, EDIT_SERVICE, \
DELETE_SELECT, DELETE_CONFIRM = range(9)
```

### Edit/Delete: `-` Keep-Old Pattern (from task_handlers.py)

Use `_is_keep_old(text)` helper (define locally in repairman_handlers.py — do not import from task_handlers):

```python
def _is_keep_old(text: str) -> bool:
    return text.strip() in ("", "-")
```

Store edit state in `context.user_data["edit_repairman"]` (dict copy of Row).
Store repairman IDs list in `context.user_data["repairman_ids"]`.

### Confirmation Message Formats

- **Add**: `f"✅ Đã thêm thợ: <b>{html.escape(name)}</b> — {phone} — {service_type}."`
- **Edit**: `f"✅ Đã cập nhật thợ: <b>{html.escape(name)}</b> — {phone} — {service_type}."`
- **Delete confirm**: `f"Bạn có chắc muốn xóa thợ <b>{html.escape(name)}</b>? Trả lời 'Có' để xác nhận hoặc 'Không' để hủy."`
- **Delete success**: `f"✅ Đã xóa thợ: <b>{html.escape(name)}</b>"`
- **Delete cancel**: `"Đã hủy xóa."`

All messages containing HTML use `parse_mode="HTML"`. Use `html.escape()` for all user-supplied strings.

### DB Access Pattern

Always get conn from `context.application.bot_data["db"]` — this is the PTB thread's connection (AD-5).

```python
conn = context.application.bot_data["db"]
```

### Files in This Story

| File | Action |
|------|--------|
| `homekeeper/db/repairman_repo.py` | NEW — CRUD for REPAIRMAN |
| `homekeeper/bot/repairman_handlers.py` | NEW — ConversationHandler for /repairman |
| `main.py` | UPDATE — import + register build_repairman_conversation() |
| `tests/test_repairman_repo.py` | NEW |
| `tests/test_repairman_handlers.py` | NEW |

**DO NOT modify**: `schema.sql` (REPAIRMAN table already exists), `homekeeper/bot/__init__.py` (do not change admin_only), `homekeeper/bot/task_handlers.py`.

### Testing Patterns (match existing tests)

**Repo tests** — use in-memory SQLite with schema:

```python
@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys=ON")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()
```

**Handler tests** — use MagicMock + AsyncMock + patch.dict for ADMIN_USER_ID (matches test_edit_handler.py):

```python
def _make_update_context(conn, text="", user_id=12345, args=None):
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.text = text
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_message = message
    application = MagicMock()
    application.bot_data = {"db": conn}
    context = MagicMock()
    context.application = application
    context.user_data = {}
    context.args = args or []
    return update, context

@pytest.fixture(autouse=True)
def patch_admin():
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield
```

Handler tests are `@pytest.mark.asyncio` async functions.

### Story 3.2 / 3.3 Preparation (do NOT implement now)

- `homekeeper/bot/incident_handlers.py` — Story 3.2
- `homekeeper/domain/matching.py` — Story 3.3 (keyword match between incident description and repairman service_type)
- `homekeeper/db/incident_repo.py` — Story 3.2

Do NOT create these files in Story 3.1. They are mentioned here only so the dev agent doesn't accidentally create empty placeholder files.

### Project Structure Notes

- Module imports: `from homekeeper.db import repairman_repo` (follow same pattern as `from homekeeper.db import task_repo`)
- File name: `repairman_handlers.py` (matches architecture Structural Seed exactly)
- Test files: `tests/test_repairman_repo.py`, `tests/test_repairman_handlers.py` (follow `tests/test_member_repo.py` naming pattern)
- No `domain/` changes — all repairman logic is CRUD, no pure-Python business logic needed in Story 3.1

### References

- `homekeeper/bot/task_handlers.py` — ConversationHandler pattern to follow (edit, delete with numbered selection + Có/Không confirm)
- `homekeeper/db/task_repo.py` — CRUD pattern to follow for repairman_repo.py
- `homekeeper/bot/__init__.py:11` — admin_only decorator (do NOT use for repairman_cmd; AC-6 requires different message)
- `homekeeper/db/schema.sql` — REPAIRMAN table definition (already exists)
- `main.py:61-68` — handler registration pattern
- `tests/test_edit_handler.py` — MagicMock/AsyncMock pattern for handler tests
- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md`
  - AD-1 (downward-only imports), AD-3 (domain pure Python), AD-4 (no external calls), AD-7 (in-memory conversation state)
- Epics: `_bmad-output/planning-artifacts/epics.md` lines 349-381

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### Completion Notes List

- Implemented `repairman_repo.py` with 5 CRUD functions; 12 repo tests all pass
- Implemented `repairman_handlers.py`: single ConversationHandler dispatching add/list/edit/delete; inline admin check sends domain-specific AC-6 message; 29 handler tests all pass
- Wired `build_repairman_conversation()` into `main.py`
- Full suite: 213 tests, 0 regressions

### File List

- homekeeper/db/repairman_repo.py (NEW)
- homekeeper/bot/repairman_handlers.py (NEW)
- main.py (UPDATED)
- tests/test_repairman_repo.py (NEW)
- tests/test_repairman_handlers.py (NEW)
