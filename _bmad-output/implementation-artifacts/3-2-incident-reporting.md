---
status: done
baseline_commit: NO_VCS
---

# Story 3.2: Incident Reporting

Status: done

## Story

As an Admin or Member,
I want to report a home incident with a free-text description,
So that the issue is logged and I can get help finding a repairman.

## Acceptance Criteria

**AC-1 — Prompt on `/incident`:**
**Given** Admin hoặc Member gửi `/incident`
**When** Bot nhận lệnh từ bất kỳ user đã xác thực (Admin hoặc Member đăng ký)
**Then** Bot hỏi: "Mô tả sự cố: (ví dụ: điều hòa phòng ngủ không mát)"

**AC-2 — Save and ask repairman:**
**Given** User nhập mô tả sự cố không rỗng
**When** Bot nhận mô tả
**Then** Bot lưu Incident vào bảng INCIDENT với `reported_by` = Telegram user ID, `description`, `created_at = now (UTC)`
**And** Bot hỏi: "Bạn có cần tìm thợ sửa không?" với nút inline "Có" và "Không"

**AC-3 — "Không" branch:**
**Given** User taps nút "Không"
**When** Bot nhận callback
**Then** Bot reply: "✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ." — flow kết thúc

**AC-4 — Empty description rejected:**
**Given** User nhập mô tả rỗng (hoặc chỉ có whitespace)
**When** Bot validate
**Then** Bot yêu cầu nhập lại, KHÔNG lưu Incident

**AC-5 — Unauthenticated user rejected:**
**Given** Một Telegram user không phải Admin và không có trong bảng MEMBER gửi `/incident`
**When** Bot kiểm tra quyền
**Then** Bot từ chối: "Bạn không có quyền sử dụng bot này."

## Tasks / Subtasks

- [x] Task 1: Tạo `homekeeper/db/incident_repo.py` với `create_incident` (AC: 2)
  - [x] 1.1 Implement `create_incident(conn, reported_by, description) -> int` — INSERT INTO INCIDENT, `created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`, commit, return `cursor.lastrowid`
  - [x] 1.2 Viết `tests/test_incident_repo.py`: create_incident returns id, persists all fields, reported_by stored, description stored, created_at is UTC string

- [x] Task 2: Implement auth helper + entry point in `homekeeper/bot/incident_handlers.py` (AC: 1, 5)
  - [x] 2.1 Define constants: `ASK_DESC = 0`, `INCIDENT_YES_PATTERN = r'^incident_yes:\d+$'`, `INCIDENT_NO_PATTERN = r'^incident_no$'`
  - [x] 2.2 Implement `_is_authenticated(user_id: int, conn) -> bool`: parse `ADMIN_USER_ID` from env (default "0", catch ValueError → return False); if `user_id == admin_id` → True; else query `member_repo.get_all_members(conn)` and check `any(m["telegram_user_id"] == user_id for m in members)`
  - [x] 2.3 Implement `incident_cmd(update, context) -> int`: guard `effective_user is None`; get conn from `context.application.bot_data["db"]`; call `_is_authenticated`; if not → reply "Bạn không có quyền sử dụng bot này." → END; else → reply "Mô tả sự cố: (ví dụ: điều hòa phòng ngủ không mát)" → return `ASK_DESC`
  - [x] 2.4 Viết tests: unauthenticated rejected with exact message, admin passes, registered member passes (insert into MEMBER table in in-memory conn), prompt text shown

- [x] Task 3: Implement description handler — save + inline keyboard (AC: 2, 4)
  - [x] 3.1 Implement `receive_description(update, context) -> int`: strip text; if empty → reply "Mô tả không được để trống. Nhập lại:" → return `ASK_DESC`; else → get conn; try `incident_repo.create_incident(conn, user_id, description)` → get `incident_id`; send inline keyboard with `InlineKeyboardMarkup([[InlineKeyboardButton("Có", callback_data=f"incident_yes:{incident_id}"), InlineKeyboardButton("Không", callback_data="incident_no")]])` with message "Bạn có cần tìm thợ sửa không?"; return `ConversationHandler.END`
  - [x] 3.2 Wrap `create_incident` call in try/except Exception; log error; reply "Không thể lưu sự cố. Vui lòng thử lại." → END on failure
  - [x] 3.3 Viết tests: empty description rejected + re-prompts; non-empty description saved (verify INCIDENT row in DB); inline keyboard sent; keyboard has "Có" and "Không"; "Có" callback_data starts with "incident_yes:"; "Không" callback_data is "incident_no"

- [x] Task 4: Implement "Không" callback + cancel + builder (AC: 3)
  - [x] 4.1 Implement `incident_no_callback(update, context) -> None`: `query = update.callback_query`; `await query.answer()`; if `query.message` → `await query.message.reply_text("✅ Đã ghi nhận sự cố. Liên hệ tôi nếu cần thêm hỗ trợ.")`
  - [x] 4.2 Implement `incident_cancel(update, context) -> int`: reply "Đã hủy." → END
  - [x] 4.3 Implement `build_incident_conversation() -> ConversationHandler`: `entry_points=[CommandHandler("incident", incident_cmd)]`, `states={ASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)]}`, `fallbacks=[CommandHandler("cancel", incident_cancel)]`
  - [x] 4.4 Viết tests: incident_no_callback calls query.answer(), sends correct "✅ Đã ghi nhận sự cố..." message

- [x] Task 5: Wire `main.py` + full suite (AC: all)
  - [x] 5.1 Add `from homekeeper.bot.incident_handlers import build_incident_conversation, incident_no_callback, INCIDENT_NO_PATTERN`
  - [x] 5.2 Add `application.add_handler(build_incident_conversation())` after `build_repairman_conversation()`
  - [x] 5.3 Add `application.add_handler(CallbackQueryHandler(incident_no_callback, pattern=INCIDENT_NO_PATTERN))` after the reminder callback handler
  - [x] 5.4 Chạy full test suite — tất cả tests GREEN, không regression

### Review Findings

- [x] [Review][Patch] ValueError in `_is_authenticated` returns False before checking MEMBER table — if `ADMIN_USER_ID` is a non-integer string, all Members are denied (AC-1 broken) [`incident_handlers.py:23-27`]
- [x] [Review][Patch] Error handler says "Vui lòng thử lại" but returns `ConversationHandler.END`, making retry impossible — fix: return `ASK_DESC` [`incident_handlers.py:60-61`]
- [x] [Review][Patch] `incident_no_callback` sends `reply_text` but leaves original keyboard active — user can re-tap "Có" after declining; fix: `edit_text` to replace keyboard message [`incident_handlers.py:76-80`]
- [x] [Review][Patch] `receive_description` accesses `update.effective_user.id` without a `None` guard — channel posts can have `effective_user=None`, causing `AttributeError` [`incident_handlers.py:54`]
- [x] [Review][Patch] `ADMIN_USER_ID` default `"0"` inconsistent with `reminder_callbacks.py` pattern — changed to `""` with logger.error + member fallback [`incident_handlers.py:25`]
- [x] [Review][Defer] `conn.commit()` inside `create_incident` — pre-existing codebase pattern across all repos; deferred
- [x] [Review][Defer] TOCTOU re-auth in `receive_description` — design choice; ConversationHandler state is per-user, re-revocation gap is acceptable; deferred
- [x] [Review][Defer] Full MEMBER table scan per auth check — optimization opportunity; not in story scope; deferred
- [x] [Review][Defer] Re-entering `/incident` mid-flow leaves dangling keyboard — standard ConversationHandler in-memory behavior (AD-7); deferred
- [x] [Review][Defer] No description length limit — pre-existing pattern across codebase; deferred
- [x] [Review][Defer] `cursor.lastrowid` returns `None` if future trigger suppresses INSERT — no current trigger exists; deferred

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

- **AD-1**: `incident_handlers.py` imports only from `db/` and `domain/` — NEVER from `scheduler/`
- **AD-4**: NO HTTP clients, NO external calls. This story is pure local bot interaction.
- **AD-7**: ConversationHandler uses default in-memory state. Restart resets mid-conversation — acceptable.
- **AD-3**: No domain logic in `domain/` for this story. Story 3.3 adds `domain/matching.py`. Story 3.2 is CRUD + inline keyboard flow.

### Critical: Auth Pattern — NOT `@admin_only`

Story 3.2 allows BOTH Admin AND registered Members. The standard `@admin_only` decorator (in `homekeeper/bot/__init__.py`) only accepts Admin. **DO NOT use `@admin_only` on `incident_cmd`.**

Instead, implement an inline `_is_authenticated` helper:

```python
def _is_authenticated(user_id: int, conn) -> bool:
    try:
        admin_id = int(os.environ.get("ADMIN_USER_ID", "0"))
    except ValueError:
        return False
    if user_id == admin_id:
        return True
    members = member_repo.get_all_members(conn)
    return any(m["telegram_user_id"] == user_id for m in members)
```

The rejection message MUST be exactly: **"Bạn không có quyền sử dụng bot này."** (same as `@admin_only` — consistent UX for unauthorized users).

### INCIDENT Table (already in schema.sql — NO SCHEMA CHANGE)

```sql
CREATE TABLE IF NOT EXISTS INCIDENT (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reported_by INTEGER NOT NULL,   -- Telegram user ID (Admin or Member)
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL    -- ISO-8601 datetime (stored UTC)
);
```

**Do NOT modify schema.sql.**

### Datetime Format

Follow the existing codebase UTC pattern from `reminder_callbacks.py:58`:
```python
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

### ConversationHandler — Single State

Only one conversation state is needed:

```python
ASK_DESC = 0
```

Flow: `incident_cmd` → `ASK_DESC` → `receive_description` → `ConversationHandler.END`

The inline keyboard callback (`incident_no_callback`) is handled **outside** the ConversationHandler as a global `CallbackQueryHandler`, following the `reminder_callbacks.py` pattern. This enables Story 3.3 to add its own `CallbackQueryHandler` for `incident_yes` without touching Story 3.2's ConversationHandler.

### Inline Keyboard Design

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Có", callback_data=f"incident_yes:{incident_id}"),
        InlineKeyboardButton("Không", callback_data="incident_no"),
    ]
])
await update.effective_message.reply_text(
    "Bạn có cần tìm thợ sửa không?",
    reply_markup=keyboard,
)
return ConversationHandler.END
```

**callback_data patterns** (export from `incident_handlers.py` for use in `main.py` and Story 3.3):
```python
INCIDENT_YES_PATTERN = r'^incident_yes:\d+$'  # Story 3.3 will register this
INCIDENT_NO_PATTERN  = r'^incident_no$'        # Story 3.2 registers this
```

Story 3.3 will import `INCIDENT_YES_PATTERN` from this file to register its own handler.

### DB Access Pattern

Always get conn from `context.application.bot_data["db"]` in ConversationHandler callbacks.
For `incident_no_callback` (global CallbackQueryHandler), use `context.application.bot_data["db"]` for consistency.

### `member_repo.get_all_members` Return Format

`member_repo.get_all_members(conn)` returns a list of `sqlite3.Row` objects (because `open_db()` sets `conn.row_factory = sqlite3.Row`). Access `m["telegram_user_id"]` by column name.

### Story 3.3 Preparation (do NOT implement now)

Story 3.3 will add:
- `homekeeper/domain/matching.py` — keyword match between incident description and repairman service_type
- `incident_yes_callback` in `incident_handlers.py` — handle the "Có" callback, call matching.py, show results
- Register `CallbackQueryHandler(incident_yes_callback, pattern=INCIDENT_YES_PATTERN)` in `main.py`

**Do NOT create `domain/matching.py` or implement `incident_yes_callback` in Story 3.2.**

### Files in This Story

| File | Action |
|------|--------|
| `homekeeper/db/incident_repo.py` | NEW — `create_incident` |
| `homekeeper/bot/incident_handlers.py` | NEW — ConversationHandler + `incident_no_callback` |
| `main.py` | UPDATE — import + register handlers |
| `tests/test_incident_repo.py` | NEW |
| `tests/test_incident_handlers.py` | NEW |

**DO NOT modify**: `schema.sql` (INCIDENT already exists), `homekeeper/bot/__init__.py`, any existing handler files.

### Testing Patterns (match Story 3.1 / existing tests)

**Repo tests** — in-memory SQLite with schema, `row_factory = sqlite3.Row`:

```python
@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "homekeeper" / "db" / "schema.sql"
    c.executescript(schema.read_text())
    yield c
    c.close()
```

**Handler tests** — MagicMock + AsyncMock for Telegram objects; real in-memory conn for DB:

```python
def _make_uc(conn, text="", user_id=12345, args=None):
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

def _make_callback_uc(conn, callback_data="incident_no", user_id=12345):
    query = MagicMock()
    query.data = callback_data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    application = MagicMock()
    application.bot_data = {"db": conn}
    context = MagicMock()
    context.application = application
    context.bot_data = {"db": conn}
    return update, context

@pytest.fixture(autouse=True)
def patch_admin():
    with patch.dict("os.environ", {"ADMIN_USER_ID": "12345"}):
        yield
```

**Member auth test** — insert real row into MEMBER table:
```python
async def test_member_can_access(conn):
    conn.execute("INSERT INTO MEMBER (telegram_user_id, name) VALUES (99999, 'Test')")
    conn.commit()
    update, context = _make_uc(conn, user_id=99999)
    result = await incident_cmd(update, context)
    assert result == ASK_DESC
```

Handler tests are `@pytest.mark.asyncio` async functions with `asyncio_mode=strict`.

### Previous Story Learnings (Story 3.1)

- Shared `user_data` key names between edit/delete flows caused state collision — use uniquely prefixed keys
- Wrap ALL DB calls in `try/except Exception` and reply with user-facing error (not just log) — matches task_handlers.py pattern
- Import pattern: `from homekeeper.db import incident_repo` (not `from homekeeper.db.incident_repo import ...`)
- `row_factory = sqlite3.Row` is set in `open_db()` — named column access works in production; tests must set it explicitly on the in-memory conn
- `@admin_only` sends "Bạn không có quyền sử dụng bot này." — this story must match that exact string for unauthenticated users (AC-5)

### Module Import Pattern

```python
from homekeeper.db import incident_repo
from homekeeper.db import member_repo
```

### handler_registration Order in main.py

Current order (after Story 3.2):
1. `build_add_conversation()`
2. `build_edit_conversation()`
3. `build_delete_conversation()`
4. `build_repairman_conversation()`
5. `build_incident_conversation()`  ← NEW
6. `CommandHandler("list", list_handler)`
7. `CommandHandler("start", start_handler)`
8. `CallbackQueryHandler(handle_reminder_callback, pattern=CALLBACK_PATTERN)`
9. `CallbackQueryHandler(incident_no_callback, pattern=INCIDENT_NO_PATTERN)`  ← NEW

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md` — AD-1, AD-3, AD-4, AD-7
- `homekeeper/bot/__init__.py` — `admin_only` decorator (do NOT use for incident_cmd)
- `homekeeper/bot/reminder_callbacks.py` — CallbackQueryHandler pattern, `query.answer()` usage, UTC datetime format
- `homekeeper/bot/repairman_handlers.py` — ConversationHandler pattern, try/except DB calls, auth inline check
- `homekeeper/db/member_repo.py` — `get_all_members` returns list of sqlite3.Row
- `homekeeper/db/connection.py:18` — `conn.row_factory = sqlite3.Row` set in `open_db()`
- `homekeeper/db/schema.sql` — INCIDENT table definition (already exists)
- `main.py:60-73` — handler registration pattern
- `tests/test_repairman_handlers.py` — MagicMock/AsyncMock pattern to follow
- Epics: `_bmad-output/planning-artifacts/epics.md` lines 383-412

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

None.

### Completion Notes List

- ✅ Task 1: `incident_repo.create_incident` — INSERT + commit + return lastrowid. UTC datetime format matches existing codebase pattern.
- ✅ Task 2: `_is_authenticated` helper checks ADMIN_USER_ID env then MEMBER table. `incident_cmd` uses it; unauthenticated gets exact "Bạn không có quyền sử dụng bot này." message.
- ✅ Task 3: `receive_description` validates non-empty, saves INCIDENT, returns inline keyboard with `incident_yes:{id}` and `incident_no` callback_data. try/except wraps DB call.
- ✅ Task 4: `incident_no_callback` answers query then sends confirmation. `build_incident_conversation` returns ConversationHandler with single `ASK_DESC` state.
- ✅ Task 5: `main.py` wired — `build_incident_conversation()` registered after repairman conversation; `incident_no_callback` registered after reminder callback handler.
- ✅ Full suite: 235/235 passed (213 pre-existing + 5 repo + 17 handler, 0 regressions).

### File List

- `homekeeper/db/incident_repo.py` (NEW)
- `homekeeper/bot/incident_handlers.py` (NEW)
- `main.py` (UPDATED)
- `tests/test_incident_repo.py` (NEW)
- `tests/test_incident_handlers.py` (NEW)
