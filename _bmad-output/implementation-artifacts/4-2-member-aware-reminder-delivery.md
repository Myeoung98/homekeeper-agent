---
status: done
baseline_commit: NO_VCS
---

# Story 4.2: Member-Aware Reminder Delivery

Status: done

## Story

As a Member,
I want to receive the same reminders as the admin without seeing management controls,
So that I stay informed about home maintenance without accidentally triggering admin actions.

## Acceptance Criteria

**AC-1 — D-1 reminder to members:**
**Given** Scheduler gửi D-1 Reminder cho một Task
**When** Có ít nhất một Member trong bảng MEMBER
**Then** Bot gửi cùng nội dung Reminder đến mỗi Member trong danh sách
**And** Tin nhắn gửi cho Member KHÔNG có inline keyboard (FR-8)

**AC-2 — D-0 reminder: admin with keyboard, members without:**
**Given** Scheduler gửi D-0 Reminder cho một Task
**When** Bot gửi đến Admin và các Member
**Then** Admin nhận Reminder kèm nút "✅ Hoàn thành" và "⏭ Bỏ qua lần này"
**And** Mỗi Member nhận cùng nội dung text nhưng không có nút inline keyboard

**AC-3 — Overdue reminder: admin with keyboard, members plain text:**
**Given** Scheduler gửi Overdue Reminder cho một Task
**When** Bot gửi đến Admin và các Member
**Then** Admin nhận ⚠️ Overdue Reminder kèm nút hành động
**And** Mỗi Member nhận thông báo overdue dạng text thuần, không có nút

**AC-4 — Removed member stops receiving:**
**Given** Admin xóa một Member khỏi bảng MEMBER
**When** Scheduler gửi Reminder tiếp theo
**Then** Member đã xóa không nhận được Reminder — bot query danh sách Member mỗi lần gửi, không cache

**AC-5 — Member send error isolated:**
**Given** Bot gửi Reminder đến một Member nhưng Telegram trả về lỗi (ví dụ: user đã block bot)
**When** Lỗi xảy ra
**Then** Bot log lỗi ở level WARNING, tiếp tục gửi đến các Member còn lại và Admin — không crash toàn bộ Reminder batch

## Tasks / Subtasks

- [x] Task 1: Verify `_check_d1` implementation against AC-1 and AC-5 (AC: 1, 5)
  - [x] 1.1 Read `homekeeper/scheduler/loop.py` `_check_d1` — confirm: text sent to all members via `get_all_members`, no `reply_markup`, per-member try/except with `logger.warning`
  - [x] 1.2 Run `python3 -m pytest tests/test_scheduler_d1.py -v` — all tests GREEN

- [x] Task 2: Verify `_check_d0` implementation against AC-2 and AC-5 (AC: 2, 5)
  - [x] 2.1 Read `_check_d0` — confirm: admin gets `reply_markup=keyboard`, members called with `reply_markup` absent (defaults to None in sender), per-member try/except with `logger.warning`
  - [x] 2.2 Run `python3 -m pytest tests/test_scheduler_d0.py -v` — all tests GREEN

- [x] Task 3: Verify `_check_overdue` implementation against AC-3 and AC-5 (AC: 3, 5)
  - [x] 3.1 Read `_check_overdue` — confirm: admin gets `admin_text` + keyboard, members get `member_text` (different: omits "Bạn đã xử lý chưa?"), per-member try/except
  - [x] 3.2 Run `python3 -m pytest tests/test_scheduler_overdue.py -v` — all tests GREEN

- [x] Task 4: Verify `catchup.py` member delivery and AC-4 (no-cache) (AC: 4)
  - [x] 4.1 Read `homekeeper/scheduler/catchup.py` `_send_catchup` — confirm: `get_all_members(conn)` called inside `_send_catchup` (fresh query each call), members get same text as admin, no keyboard
  - [x] 4.2 Verify AC-4: `get_all_members` is called inside each tick-check and inside `_send_catchup` (not cached at module level or passed in) — dynamic query means removed members are excluded immediately
  - [x] 4.3 Run `python3 -m pytest tests/test_scheduler_catchup.py -v` — all tests GREEN

- [x] Task 5: Run full test suite — no regressions (AC: all)
  - [x] 5.1 Run `python3 -m pytest tests/ -q` — all 293 tests GREEN, zero regressions

### Review Findings

- [x] [Review][Patch] D-1 member test missing `reply_markup is None` assertion — `test_check_d1_sends_to_members` does not verify member calls have no keyboard (AC-1 gap); `test_check_d0_members_receive_no_keyboard` has the equivalent D-0 check; a future regression adding `reply_markup` to D-1 member sends would go undetected [tests/test_scheduler_d1.py] (source: edge)
- [x] [Review][Defer] `_check_d0` uses `any_sent_on_date` (type-agnostic) while `_check_d1` uses type-specific key — a catchup/overdue row on the same calendar day would suppress D-0; pre-existing asymmetry since Stories 2.2/2.3 [homekeeper/scheduler/loop.py]
- [x] [Review][Defer] AC-4 "fresh query per send" property not explicitly tested for catchup/overdue paths — structural correctness verified by code inspection; no test deletes a member between admin send and member loop [tests/test_scheduler_catchup.py, tests/test_scheduler_overdue.py]
- [x] [Review][Defer] AC-5 `WARNING` log level not asserted in any test — tests verify iteration continues but never assert `caplog` / `logger.warning` was called; a silent swallow (DEBUG or bare except) would pass [tests/test_scheduler_d1.py, test_scheduler_d0.py, test_scheduler_overdue.py, test_scheduler_catchup.py]
- [x] [Review][Defer] `test_check_overdue_sends_when_overdue` asserts `call_count == 1` vacuously — no members in fixture; passes correctly today but gives false confidence that only admin receives; should assert `chat_id == admin_id` explicitly [tests/test_scheduler_overdue.py:57]

## Dev Notes

### ⚡ Pre-Implementation Notice — Verify, Don't Rebuild

**This story's implementation was pre-built during Stories 2.2–2.5.** ALL scheduler files already send to members. Your job is to VERIFY the existing code satisfies each AC and that all tests pass.

**DO NOT** rewrite, refactor, or add new functions. Read each file, confirm the AC, run the tests, check them off.

### Architecture Constraints

- **AD-1**: `scheduler/` imports `db/` only — `loop.py` may NOT import from `bot/`
- **AD-2**: `bot/` and `scheduler/` communicate through SQLite only
- **AD-5**: Scheduler thread opens its own DB connection via `open_db()` — never shares `bot_data["db"]`
- **FR-8**: Members receive text-only reminders (no inline keyboard) — enforced by calling `send_telegram_message(id, text)` without `reply_markup`

### Current Implementation — `loop.py`

**`_check_d1`** (member fan-out, lines ~50–75):
```python
# Log first, then members best-effort
sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
reminder_log_repo.log_sent(conn, task_id, "D-1", sent_at)
members = member_repo.get_all_members(conn)
for member in members:
    try:
        sender.send_telegram_message(member["telegram_user_id"], text)
    except Exception as exc:
        logger.warning("Failed to send D-1 to member %d: %s", member["telegram_user_id"], exc)
```
- Same `text` as admin (no keyboard for members, because `send_telegram_message` default `reply_markup=None`)

**`_check_d0`** (member fan-out, lines ~100–125):
```python
# Admin gets keyboard; members get plain text
sender.send_telegram_message(admin_id, text, reply_markup=keyboard)
# ... log ...
members = member_repo.get_all_members(conn)
for member in members:
    try:
        sender.send_telegram_message(member["telegram_user_id"], text)  # no reply_markup
    except Exception as exc:
        logger.warning("Failed to send D-0 to member %d: %s", member["telegram_user_id"], exc)
```

**`_check_overdue`** (different text for members):
```python
admin_text = f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> đã trễ {n} ngày. Bạn đã xử lý chưa?"
member_text = f"⚠️ Quá hạn: <b>{html.escape(task['name'])}</b> đã trễ {n} ngày."
# Admin gets admin_text + keyboard; members get member_text, no keyboard
```

### Current Implementation — `catchup.py`

**`_send_catchup`** (member fan-out at end):
```python
members = member_repo.get_all_members(conn)
for member in members:
    try:
        sender.send_telegram_message(member["telegram_user_id"], text)
    except Exception as exc:
        logger.warning("Catch-up member send failed %d: %s", member["telegram_user_id"], exc)
```
- `get_all_members` is called inside `_send_catchup`, not cached — satisfies AC-4

### AC-4: No-Cache Guarantee

AC-4 requires "bot query danh sách Member mỗi lần gửi, không cache". Verify by reading the call sites:
- `_check_d1`: `member_repo.get_all_members(conn)` called inside the function body each invocation
- `_check_d0`: same pattern
- `_check_overdue`: same pattern
- `_send_catchup`: same pattern

No module-level `members` variable exists — the query is always fresh.

### Test Coverage Map

| AC | Test file | Key test functions |
|----|-----------|-------------------|
| AC-1 | `test_scheduler_d1.py` | `test_check_d1_sends_to_members`, `test_check_d1_continues_on_member_failure` |
| AC-2 | `test_scheduler_d0.py` | `test_check_d0_admin_receives_keyboard`, `test_check_d0_members_receive_no_keyboard`, `test_check_d0_sends_to_admin_and_all_members`, `test_check_d0_continues_on_member_failure` |
| AC-3 | `test_scheduler_overdue.py` | `test_check_overdue_admin_receives_keyboard`, `test_check_overdue_members_receive_no_keyboard`, `test_check_overdue_member_text_truncated` |
| AC-4 | Architectural (fresh query per call) | N/A — no dedicated test needed; code structure guarantees it |
| AC-5 | `test_scheduler_d1.py`, `test_scheduler_d0.py`, `test_scheduler_overdue.py`, `test_scheduler_catchup.py` | `*_continues_on_member_failure`, `*_member_send_failure` |

### Files in This Story

| File | Action |
|------|--------|
| `homekeeper/scheduler/loop.py` | VERIFY only — no changes expected |
| `homekeeper/scheduler/catchup.py` | VERIFY only — no changes expected |
| `tests/test_scheduler_d1.py` | VERIFY only — tests already exist |
| `tests/test_scheduler_d0.py` | VERIFY only — tests already exist |
| `tests/test_scheduler_overdue.py` | VERIFY only — tests already exist |
| `tests/test_scheduler_catchup.py` | VERIFY only — tests already exist |

**DO NOT modify**: `member_repo.py` (already correct), `sender.py` (already correct), any bot handler.

### Previous Story Learnings (from Story 4.1)

1. **`get_all_members` already existed** before Story 4.1 — it was the reason Story 4.1 had to avoid duplicating it. This function is the exact one used in all four scheduler fan-out loops.
2. **Member fan-out pattern established in Stories 2.2–2.5**: `log_sent` is written AFTER admin send succeeds and BEFORE member loop — member failures do not roll back the log.
3. **293 tests passing after Story 4.1**: all scheduler tests were already GREEN including member delivery tests. This story's full suite target is also 293 (no new code = no new tests needed).

### References

- `homekeeper/scheduler/loop.py` — `_check_d1`, `_check_d0`, `_check_overdue`
- `homekeeper/scheduler/catchup.py` — `_send_catchup`
- `homekeeper/db/member_repo.py` — `get_all_members` (the function used in all fan-outs)
- `tests/test_scheduler_d1.py`, `tests/test_scheduler_d0.py`, `tests/test_scheduler_overdue.py`, `tests/test_scheduler_catchup.py`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- Story 4.2 is a verification-only story. All 5 ACs were pre-implemented during Stories 2.2–2.5 in `loop.py` and `catchup.py`. Verified each AC against the existing code:
  - AC-1: `_check_d1` fans out to all members via `get_all_members(conn)`, text only, no keyboard — 12/12 tests GREEN.
  - AC-2: `_check_d0` sends admin with `reply_markup=keyboard`, members without — 12/12 tests GREEN.
  - AC-3: `_check_overdue` sends admin `admin_text` + keyboard, members get shorter `member_text` without keyboard — 16/16 tests GREEN.
  - AC-4: `get_all_members` is called inside the body of each send function (not cached) — fresh query each tick guarantees removed members are excluded immediately.
  - AC-5: all four fan-out loops (`_check_d1`, `_check_d0`, `_check_overdue`, `_send_catchup`) wrap each member send in `try/except Exception` with `logger.warning` — failure of one member does not abort the batch.
- Full suite: 293/293 passed, zero regressions.

### File List

- `homekeeper/scheduler/loop.py` (verified — no changes)
- `homekeeper/scheduler/catchup.py` (verified — no changes)
- `tests/test_scheduler_d1.py` (verified — no changes)
- `tests/test_scheduler_d0.py` (verified — no changes)
- `tests/test_scheduler_overdue.py` (verified — no changes)
- `tests/test_scheduler_catchup.py` (verified — no changes)

### Change Log

- 2026-07-05: Story 4.2 verified — pre-built member delivery in scheduler confirmed against all 5 ACs, 293/293 tests passing.
