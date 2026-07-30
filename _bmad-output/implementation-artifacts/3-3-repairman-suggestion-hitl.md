---
status: done
baseline_commit: NO_VCS
---

# Story 3.3: Repairman Suggestion (HITL)

Status: done

## Story

As an Admin or Member,
I want the bot to suggest matching repairmen based on the incident description,
So that I have contact info ready to call — and the bot never contacts anyone on my behalf.

## Acceptance Criteria

**AC-1 — Keyword match on "Có":**
**Given** User trả lời "Có" khi được hỏi có cần tìm thợ sau khi báo Incident
**When** Bot thực hiện keyword match giữa mô tả sự cố và trường `service_type` của tất cả Repairman trong DB
**Then** Bot trả về danh sách Repairman có service_type khớp (tối thiểu 1 từ khóa chung), hiển thị: tên, số điện thoại, loại dịch vụ
**And** Kết quả xuất hiện trong ≤ 30 giây kể từ khi user xác nhận "Có" (NFR-1 — met trivially, all local)

**AC-2 — HITL enforcement (no auto-contact):**
**Given** Kết quả được trả về
**When** Bot hiển thị danh sách Repairman gợi ý
**Then** Bot KHÔNG có nút "Gọi ngay", KHÔNG tự gọi điện, KHÔNG gửi tin nhắn đến thợ — chỉ hiển thị số điện thoại để user tự liên hệ (FR-11, AD-4)
**And** Bot thêm chú thích: "Liên hệ trực tiếp với thợ theo số điện thoại trên."

**AC-3 — No matching repairmen:**
**Given** Không có Repairman nào trong DB có service_type khớp với từ khóa trong mô tả
**When** Keyword match trả về rỗng
**Then** Bot trả về: "Không tìm thấy thợ phù hợp trong danh bạ. Bạn có thể thêm thợ bằng /repairman add."

**AC-4 — Empty repairman DB:**
**Given** Danh bạ Repairman hoàn toàn rỗng (chưa nhập thợ nào)
**When** User yêu cầu tìm thợ
**Then** Bot trả về: "Danh bạ thợ đang trống. Admin có thể thêm thợ bằng /repairman add." — không crash, không trả về danh sách rỗng im lặng

## Tasks / Subtasks

- [x] Task 1: Add `get_incident_by_id` to `homekeeper/db/incident_repo.py` (AC: 1)
  - [x] 1.1 Implement `get_incident_by_id(conn, incident_id: int)` — `SELECT id, reported_by, description, created_at FROM INCIDENT WHERE id = ?`; return `cursor.fetchone()` (None if not found)
  - [x] 1.2 Viết tests in `tests/test_incident_repo.py`: returns correct row for existing id, returns None for missing id, row has correct `description` field

- [x] Task 2: Create `homekeeper/domain/` package and `matching.py` (AC: 1, AD-3)
  - [x] 2.1 Create `homekeeper/domain/__init__.py` (empty — just package init)
  - [x] 2.2 Implement `match_repairmen(description: str, repairmen) -> list` in `homekeeper/domain/matching.py`: tokenize description and each `r["service_type"]` by lowercased whitespace split; return repairmen where `set(desc_words) & set(service_words)` is non-empty (≥1 word in common); NO imports of telegram, sqlite3, or third-party — standard library only
  - [x] 2.3 Viết `tests/test_matching.py`: match returns repairman with overlapping word, case-insensitive match, no match returns empty list, empty repairmen input returns empty list, multiple repairmen filtered correctly

- [x] Task 3: Add `incident_yes_callback` to `homekeeper/bot/incident_handlers.py` (AC: 1, 2, 3, 4)
  - [x] 3.1 Add imports: `from homekeeper.db import repairman_repo` and `from homekeeper.domain import matching`
  - [x] 3.2 Implement `incident_yes_callback(update, context) -> None`:
    - `query = update.callback_query; await query.answer()`
    - Parse `incident_id = int(query.data.split(":")[1])` — wrap in try/except ValueError → `edit_text("Dữ liệu không hợp lệ.")` → return
    - Get conn from `context.application.bot_data["db"]`
    - Load incident: `incident_repo.get_incident_by_id(conn, incident_id)` — try/except; if None → edit "Không tìm thấy sự cố." → return
    - Load repairmen: `repairman_repo.get_all_repairmen(conn)` — try/except
    - AC-4: if not repairmen → edit "Danh bạ thợ đang trống. Admin có thể thêm thợ bằng /repairman add." → return
    - Match: `matches = matching.match_repairmen(incident["description"], repairmen)`
    - AC-3: if not matches → edit "Không tìm thấy thợ phù hợp trong danh bạ. Bạn có thể thêm thợ bằng /repairman add." → return
    - AC-1+2: format result lines then edit message (see format spec in Dev Notes); NO inline buttons; add footnote "Liên hệ trực tiếp với thợ theo số điện thoại trên."
    - All message sends use `query.message.edit_text(...)` — NOT `reply_text`
  - [x] 3.3 Viết tests in `tests/test_incident_handlers.py`: "Có" with matching repairman shows results, "Có" with empty DB shows AC-4 message, "Có" with no match shows AC-3 message, result message contains name + phone + service_type, result message contains footnote, no buttons in result (edit_text called with no reply_markup), DB error on repairman load replies gracefully

- [x] Task 4: Wire `main.py` + full suite (AC: all)
  - [x] 4.1 Add `incident_yes_callback, INCIDENT_YES_PATTERN` to existing import from `homekeeper.bot.incident_handlers`
  - [x] 4.2 Add `application.add_handler(CallbackQueryHandler(incident_yes_callback, pattern=INCIDENT_YES_PATTERN))` after the `incident_no_callback` handler
  - [x] 4.3 Chạy full test suite — tất cả tests GREEN, không regression

### Review Findings

- [x] [Review][Patch] Auth gap resolved: add `_is_authenticated` guard to `incident_yes_callback` — unauthenticated users could receive repairman contact info via crafted callback data [homekeeper/bot/incident_handlers.py:81]
- [x] [Review][Patch] `match_repairmen` does not strip punctuation — tokens like `"hỏng."` or `"lạnh,"` fail to match `"hỏng"` / `"lạnh"` in `service_type`; AC-1 silently fails for punctuated descriptions [homekeeper/domain/matching.py:1] (sources: blind+edge+auditor)
- [x] [Review][Patch] `_seed_incident` test helper bypasses `create_incident` — raw INSERT diverges from production; future schema changes break tests silently [tests/test_incident_handlers.py:288] (source: blind)
- [x] [Review][Patch] No test for `query.message is None` on any early-exit branch — removing `if query.message is not None` guards would not be caught by tests [tests/test_incident_handlers.py] (source: blind)
- [x] [Review][Defer] Double-tap `BadRequest: message is not modified` — second `edit_text` call on already-edited message propagates unhandled [incident_handlers.py] — deferred, PTB-level edge case
- [x] [Review][Defer] Result message can exceed Telegram 4096-char limit with many matched repairmen — deferred, low probability for home-maintenance scale
- [x] [Review][Defer] Vietnamese word segmentation: `split()` matches individual syllables, not compound words — deferred, requires domain-specific NLP library (out of scope)
- [x] [Review][Defer] Stopword false positives in set-intersection (common words like "nước" match across unrelated service types) — deferred, design limitation
- [x] [Review][Defer] No try/except around final `edit_text` call — consistent with pre-existing `incident_no_callback` pattern — deferred, pre-existing
- [x] [Review][Defer] No log entry when `query.message is None` on error paths — consistent with `incident_no_callback` pattern — deferred, pre-existing

## Dev Notes

### Architecture Constraints (MUST FOLLOW)

- **AD-1**: `incident_handlers.py` imports from `db/` and `domain/` — never from `scheduler/`. `matching.py` imports from nothing external.
- **AD-3**: `homekeeper/domain/matching.py` — standard library ONLY. No `import telegram`, `import sqlite3`, no third-party. Must be testable with plain dicts, no DB required.
- **AD-4**: HITL structural enforcement — NO HTTP client, NO external API, NO auto-dial. The bot only sends Telegram messages. The result message contains phone numbers for the user to call themselves.

### Flow: Where Story 3.3 Plugs In

Story 3.2 ends by sending the "Bạn có cần tìm thợ sửa không?" message with buttons `incident_yes:{incident_id}` and `incident_no`. Story 3.3 registers `incident_yes_callback` as a global `CallbackQueryHandler` in `main.py` using `INCIDENT_YES_PATTERN` (already defined and exported from `incident_handlers.py`).

When user taps "Có":
1. PTB routes to `incident_yes_callback` (pattern `^incident_yes:\d+$`)
2. Parse `incident_id` from `callback_data`
3. Load incident description from DB (need `get_incident_by_id` — add to `incident_repo.py`)
4. Load all repairmen from DB (`repairman_repo.get_all_repairmen`)
5. Call `matching.match_repairmen(description, repairmen)`
6. Edit the "Bạn có cần tìm thợ?" message in-place with results

### Result Message Format

Use `query.message.edit_text(...)` — this replaces the button message, removing the "Có"/"Không" buttons. Consistent with `incident_no_callback` pattern.

**With matches (AC-1 + AC-2):**
```
🔧 Thợ sửa gợi ý:

1. Nguyễn Văn A — Điều hòa — 0901234567
2. Trần B — Điện lạnh — 0987654321

Liên hệ trực tiếp với thợ theo số điện thoại trên.
```

Format per repairman: `{i}. {name} — {service_type} — {phone}`

Build using:
```python
lines = ["🔧 Thợ sửa gợi ý:\n"]
for i, r in enumerate(matches, 1):
    lines.append(f"{i}. {r['name']} — {r['service_type']} — {r['phone']}")
lines.append("\nLiên hệ trực tiếp với thợ theo số điện thoại trên.")
await query.message.edit_text("\n".join(lines))
```

**No match (AC-3):** `"Không tìm thấy thợ phù hợp trong danh bạ. Bạn có thể thêm thợ bằng /repairman add."`

**Empty DB (AC-4):** `"Danh bạ thợ đang trống. Admin có thể thêm thợ bằng /repairman add."`

### `homekeeper/domain/matching.py` — Pure Python

```python
def match_repairmen(description: str, repairmen) -> list:
    desc_words = set(description.lower().split())
    return [
        r for r in repairmen
        if desc_words & set(r["service_type"].lower().split())
    ]
```

- No imports at all (empty import section) — pure standard library computation
- Works with `sqlite3.Row` objects (subscript access) OR plain dicts (tests use plain dicts)
- Case-insensitive via `.lower()`
- Word-level tokenization via `.split()` (whitespace)
- Returns a new list — does not mutate input

### `homekeeper/domain/__init__.py`

Create as an **empty file** — just makes `homekeeper/domain` a Python package. Check if the directory exists first:
```bash
ls homekeeper/domain/
```
If the directory does not exist, create it before writing files.

### `incident_repo.get_incident_by_id` — New Function

Add to `homekeeper/db/incident_repo.py`:
```python
def get_incident_by_id(conn: sqlite3.Connection, incident_id: int):
    cursor = conn.execute(
        "SELECT id, reported_by, description, created_at FROM INCIDENT WHERE id = ?",
        (incident_id,),
    )
    return cursor.fetchone()
```

Returns `sqlite3.Row` if found, `None` if not. Access via `incident["description"]`.

### `INCIDENT_YES_PATTERN` — Already Exported from Story 3.2

`incident_handlers.py` already has:
```python
INCIDENT_YES_PATTERN = r'^incident_yes:\d+$'
```

This was defined in Story 3.2 specifically for Story 3.3 to consume. Import it in `main.py` alongside the existing imports:
```python
from homekeeper.bot.incident_handlers import (
    INCIDENT_NO_PATTERN,
    INCIDENT_YES_PATTERN,       # ADD
    build_incident_conversation,
    incident_no_callback,
    incident_yes_callback,      # ADD
)
```

### Handler Registration Order in `main.py` (after Story 3.3)

```python
application.add_handler(CallbackQueryHandler(handle_reminder_callback, pattern=CALLBACK_PATTERN))
application.add_handler(CallbackQueryHandler(incident_no_callback, pattern=INCIDENT_NO_PATTERN))
application.add_handler(CallbackQueryHandler(incident_yes_callback, pattern=INCIDENT_YES_PATTERN))  # ADD
```

### Import Order in `incident_handlers.py`

Current imports: `incident_repo`, `member_repo`. Add:
```python
from homekeeper.db import incident_repo, member_repo, repairman_repo
from homekeeper.domain import matching
```

AD-1 confirms: `bot/` may import from `db/` and `domain/`. ✅

### Callback Data Parsing

`query.data` will be e.g. `"incident_yes:42"`. Parse:
```python
try:
    incident_id = int(query.data.split(":")[1])
except (IndexError, ValueError):
    if query.message is not None:
        await query.message.edit_text("Dữ liệu không hợp lệ.")
    return
```

In practice, PTB only routes to this handler when pattern `^incident_yes:\d+$` matches, so the int conversion can never fail. Guard is belt-and-suspenders only.

### `repairman_repo.get_all_repairmen` Return Format

Returns list of `sqlite3.Row` with columns: `id, name, phone, service_type`. Access by name: `r["name"]`, `r["phone"]`, `r["service_type"]`. Empty list if no repairmen registered.

### Test Helper for `incident_yes_callback`

The callback update structure is the same as `incident_no_callback` — use `_make_callback_uc` from `test_incident_handlers.py`, passing `callback_data=f"incident_yes:{incident_id}"`. The `query.message.edit_text` mock is already set up in `_make_callback_uc` (added in Story 3.2 patch).

```python
def _make_callback_uc(conn, callback_data="incident_no", user_id=12345):
    query = MagicMock()
    query.data = callback_data
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.reply_text = AsyncMock()
    query.message.edit_text = AsyncMock()   # ← already present from Story 3.2 patch
    ...
```

**Test pattern for `incident_yes_callback`:**
```python
@pytest.mark.asyncio
async def test_incident_yes_shows_matching_repairman(conn):
    # Seed data
    conn.execute("INSERT INTO INCIDENT (reported_by, description, created_at) VALUES (12345, 'điều hòa hỏng', '2026-07-05T00:00:00Z')")
    conn.execute("INSERT INTO REPAIRMAN (name, phone, service_type) VALUES ('Anh A', '0901', 'điều hòa')")
    conn.commit()
    incident_id = conn.execute("SELECT id FROM INCIDENT").fetchone()["id"]
    update, context = _make_callback_uc(conn, callback_data=f"incident_yes:{incident_id}")
    await incident_yes_callback(update, context)
    update.callback_query.message.edit_text.assert_called_once()
    text = update.callback_query.message.edit_text.call_args[0][0]
    assert "Anh A" in text
    assert "0901" in text
    assert "điều hòa" in text
    assert "Liên hệ trực tiếp" in text
```

### `test_matching.py` — Pure Python, No DB, No Telegram

```python
def test_match_returns_repairman_with_overlapping_word():
    repairmen = [{"name": "A", "phone": "0901", "service_type": "điều hòa lạnh"}]
    result = matching.match_repairmen("điều hòa phòng ngủ không mát", repairmen)
    assert len(result) == 1

def test_match_case_insensitive():
    repairmen = [{"name": "B", "phone": "0902", "service_type": "Điện Lạnh"}]
    result = matching.match_repairmen("điện lạnh bị hỏng", repairmen)
    assert len(result) == 1

def test_no_match_returns_empty():
    repairmen = [{"name": "C", "phone": "0903", "service_type": "ống nước"}]
    result = matching.match_repairmen("điều hòa hỏng", repairmen)
    assert result == []

def test_empty_repairmen_returns_empty():
    result = matching.match_repairmen("bất kỳ mô tả", [])
    assert result == []

def test_multiple_repairmen_filtered():
    repairmen = [
        {"name": "A", "phone": "0901", "service_type": "điều hòa"},
        {"name": "B", "phone": "0902", "service_type": "ống nước"},
    ]
    result = matching.match_repairmen("điều hòa bị hỏng", repairmen)
    assert len(result) == 1
    assert result[0]["name"] == "A"
```

### Files in This Story

| File | Action |
|------|--------|
| `homekeeper/domain/__init__.py` | NEW — empty package init |
| `homekeeper/domain/matching.py` | NEW — `match_repairmen` |
| `homekeeper/db/incident_repo.py` | UPDATE — add `get_incident_by_id` |
| `homekeeper/bot/incident_handlers.py` | UPDATE — add `incident_yes_callback` + new imports |
| `main.py` | UPDATE — import + register `incident_yes_callback` |
| `tests/test_matching.py` | NEW |
| `tests/test_incident_repo.py` | UPDATE — add `get_incident_by_id` tests |
| `tests/test_incident_handlers.py` | UPDATE — add `incident_yes_callback` tests |

**DO NOT modify**: `schema.sql` (no schema change needed), `homekeeper/bot/__init__.py`, any other existing file.

### Story 3.2 Learnings (Code Review Patches)

Story 3.2 went through a code review that found 5 patches. Apply these learnings to Story 3.3:

1. **`_is_authenticated` ValueError** — fixed in 3.2: use `""` default + `logger.error` + proceed to member check. Story 3.3 does not call `_is_authenticated` (callback handlers don't re-auth — same pattern as `reminder_callbacks.py`).
2. **Error handler returns END vs ASK_DESC** — Story 3.3 uses `return` (not ConversationHandler states), so this is N/A.
3. **`edit_text` not `reply_text` for callbacks** — Story 3.3 MUST use `query.message.edit_text(...)` throughout. This removes the keyboard and replaces the message in-place.
4. **`effective_user` None guard in state handlers** — Story 3.3's `incident_yes_callback` doesn't need this since it only reads `query.data` (not `effective_user`).
5. **ADMIN_USER_ID default** — already fixed in 3.2's `_is_authenticated`. N/A here.

### No Auth Check in `incident_yes_callback`

Following the `incident_no_callback` and `reminder_callbacks.py` patterns: callback handlers do NOT re-call `_is_authenticated`. Auth was verified when the user completed `/incident`. The inline keyboard only appears to users who passed auth. A crafted `incident_yes:N` callback by an unauthenticated user would produce a harmless text reply.

### References

- Architecture: `_bmad-output/planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md` — CAP-4, AD-1, AD-3, AD-4
- `homekeeper/bot/incident_handlers.py` (current) — `INCIDENT_YES_PATTERN`, `_is_authenticated`, `incident_no_callback` pattern
- `homekeeper/db/repairman_repo.py` — `get_all_repairmen` returns list of sqlite3.Row (id, name, phone, service_type)
- `homekeeper/db/incident_repo.py` (current) — `create_incident`; add `get_incident_by_id` here
- `homekeeper/db/schema.sql` — REPAIRMAN table (id, name, phone, service_type), INCIDENT table
- `main.py` (current) — existing handler registration order
- `tests/test_incident_handlers.py` — `_make_callback_uc` helper (has `edit_text = AsyncMock()`)
- Epics: `_bmad-output/planning-artifacts/epics.md` — Story 3.3 section

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Task 1: Added `get_incident_by_id` to `incident_repo.py`. Returns sqlite3.Row or None. 3 new tests added (8 total in test_incident_repo.py), all GREEN.
- Task 2: `homekeeper/domain/` package already existed; created `matching.py` with pure-Python `match_repairmen`. 7 tests in `tests/test_matching.py`, all GREEN. No imports (standard library only, AD-3 compliant).
- Task 3: Added `incident_yes_callback` to `incident_handlers.py` with new imports. Uses `edit_text` throughout (not `reply_text`). Handles AC-1 (match), AC-2 (no buttons), AC-3 (no match), AC-4 (empty DB), plus DB error paths. 8 new tests added (28 total in test_incident_handlers.py), all GREEN.
- Task 4: Wired `main.py` — added `INCIDENT_YES_PATTERN` and `incident_yes_callback` import + handler registration. Full suite: **256/256 passed**, zero regressions.

### File List

- `homekeeper/domain/matching.py` (NEW)
- `homekeeper/db/incident_repo.py` (UPDATED — added `get_incident_by_id`)
- `homekeeper/bot/incident_handlers.py` (UPDATED — added imports + `incident_yes_callback`)
- `main.py` (UPDATED — added import + handler registration)
- `tests/test_matching.py` (NEW)
- `tests/test_incident_repo.py` (UPDATED — added 3 tests)
- `tests/test_incident_handlers.py` (UPDATED — added 8 tests)
