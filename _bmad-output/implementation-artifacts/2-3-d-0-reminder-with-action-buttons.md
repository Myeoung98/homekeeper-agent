---
baseline_commit: NO_VCS
---

# Story 2.3: D-0 Reminder with Action Buttons

Status: done

## Story

As the Admin of HomeKeeper,
I want to receive a D-0 reminder message with action buttons on the task's due date,
so that I can immediately mark the task done or skip it with one tap, and Members also get a text-only reminder.

## Acceptance Criteria

1. When a Task's `next_due_date` is **today** (VN time, after 08:00) and no `REMINDER_LOG` row of `type='D-0'` exists for that task on today's date, the scheduler sends Admin: `"📅 Đến hạn hôm nay: <b>[tên Task]</b> (DD/MM/YYYY)."` with an inline keyboard containing buttons `"✅ Hoàn thành"` (`callback_data="done:{task_id}:{due_date}"`) and `"⏭ Bỏ qua lần này"` (`callback_data="skip:{task_id}:{due_date}"`), and writes a `REMINDER_LOG` row `type='D-0'`.
2. All registered Members receive the same text message **without** an inline keyboard (FR-8).
3. Subsequent scheduler ticks on the same due date do NOT resend the D-0 reminder (idempotency via `REMINDER_LOG`).

## Tasks / Subtasks

- [x] Task 1: Extend `sender.py` to support `reply_markup` (backward-compatible) (AC: 1, 2)
  - [x] 1.1 Update `tests/test_sender.py`: modify the existing `test_send_telegram_message_calls_bot_with_correct_args` assertion to include `reply_markup=None`, and add two new tests: `test_send_telegram_message_passes_reply_markup` (verifies markup is forwarded) and `test_send_telegram_message_no_markup_by_default` (verifies `reply_markup=None` is passed when omitted). Confirm the updated + new tests fail first.
  - [x] 1.2 Update `homekeeper/scheduler/sender.py`: add `reply_markup=None` parameter to `send_telegram_message`; pass it through to `bot.send_message`. No other changes.
  - [x] 1.3 Run `python -m pytest tests/test_sender.py -v` — all 5 tests green.

- [x] Task 2: Implement `_check_d0` in `loop.py` (AC: 1, 2, 3)
  - [x] 2.1 Create `tests/test_scheduler_d0.py` with all 12 tests listed in Dev Notes (see § Test Catalogue below). Run them — all 12 must FAIL before implementation.
  - [x] 2.2 Add imports to `homekeeper/scheduler/loop.py`: `from telegram import InlineKeyboardButton, InlineKeyboardMarkup` (top-level, alongside existing imports).
  - [x] 2.3 Implement `_check_d0(conn, task) -> None` in `loop.py` following the exact spec in Dev Notes (§ `_check_d0` Implementation). Insert after `_check_d1` definition.
  - [x] 2.4 Run `python -m pytest tests/test_scheduler_d0.py -v` — all 12 tests green.

- [x] Task 3: Wire `_check_d0` into `_tick` (AC: 1, 2, 3)
  - [x] 3.1 Update `_tick` in `loop.py`: compute `today = _now.date()`, add `if due == today: _check_d0(conn, task)` branch inside the task loop, remove the `# Story 2.3: add D-0 check here` placeholder comment.
  - [x] 3.2 Run `python -m pytest tests/test_scheduler_d0.py tests/test_scheduler_d1.py tests/test_sender.py -v` — all tests green, no regressions.

- [x] Task 4: Full verification (AC: 1, 2, 3)
  - [x] 4.1 Run `python -m pytest tests/ -v` — entire suite green (no regressions in any prior story's tests).
  - [x] 4.2 Update story Status to `review`.

### Review Findings

- [x] [Review][Patch] Unused `mock_d0` variable in `test_tick_does_not_send_d0_for_task_due_tomorrow` [tests/test_scheduler_d0.py:72]
- [x] [Review][Defer] Admin double delivery if ADMIN_USER_ID is also in MEMBER table [loop.py] — deferred, pre-existing in `_check_d1`
- [x] [Review][Defer] `ADMIN_USER_ID` KeyError/ValueError aborts entire `_tick` loop [loop.py] — deferred, pre-existing in `_check_d1`
- [x] [Review][Defer] `TELEGRAM_BOT_TOKEN` KeyError propagates uncaught from sender.py — deferred, pre-existing since Story 2.2
- [x] [Review][Defer] REMINDER_LOG written before member fan-out completes (partial delivery) [loop.py] — deferred, by design (D4 from Story 2.2)
- [x] [Review][Defer] `Bot.__aenter__` issues extra `getMe` API call per send [sender.py] — deferred, pre-existing (D5 from Story 2.2)
- [x] [Review][Defer] Stale keyboard buttons remain active after task cycle advances [loop.py] — deferred, Story 2.4 cross-story contract; handler must validate `due_date` in callback_data
- [x] [Review][Defer] SQLite `date(sent_at)` fragile to future `sent_at` format drift [reminder_log_repo.py] — deferred, current code correct; future design risk only
- [x] [Review][Defer] Scheduler down on D-0 day silently drops the reminder — deferred, Story 2.5 scope (catch-up logic)

## Dev Notes

### Architecture Constraints (MUST follow)

- **AD-1**: `scheduler/` MAY import from `telegram` library (third-party). MUST NOT import from `homekeeper.bot`.
- **AD-2**: Bot ↔ Scheduler communication is SQLite-only. `_check_d0` writes only to `REMINDER_LOG`.
- **AD-5**: `_check_d0` / `_tick` always receive the single `conn` opened by `_run_loop` — never call `open_db()` inside check functions.
- **AD-8**: Scheduler is **read-only on TASK**. After deciding to send, call `_task_unchanged(conn, task_id, due_date)` before writing `REMINDER_LOG` (same pattern as `_check_d1`).

### Existing Code to Understand Before Touching

**`homekeeper/scheduler/loop.py`** — current `_check_d1` is the exact mirror for `_check_d0`. Read it completely. Key patterns to replicate:
- Operation order: `already_sent` → `_task_unchanged` → admin send → `log_sent` → member loop
- Log on success (`logger.info`), log on admin failure (`logger.error`) + early return, log on member failure (`logger.warning`) + continue
- `sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` (Z suffix — patch P2 from Story 2.2)

**`homekeeper/scheduler/sender.py`** — current signature: `send_telegram_message(chat_id: int, text: str)`. Task 1 extends this to `send_telegram_message(chat_id: int, text: str, reply_markup=None)`. The `reply_markup=None` default makes all existing D-1 call-sites backward-compatible with zero changes.

**`tests/test_scheduler_d1.py`** — read the full file for helper function signatures and fixture patterns to copy verbatim into `tests/test_scheduler_d0.py`. Key helpers: `tomorrow_str()`, `today_str()`, `make_vn_time(hour, minute)`.

### `_check_d0` Implementation (exact spec)

```python
def _check_d0(conn, task) -> None:
    """Send D-0 reminder if not yet sent for this task's current due-date cycle."""
    task_id = task["id"]
    due_date = task["next_due_date"]  # YYYY-MM-DD

    # D-0 fires on the due date itself — reminder_date == due_date
    reminder_date = due_date

    if reminder_log_repo.already_sent(conn, task_id, "D-0", reminder_date):
        return

    if not _task_unchanged(conn, task_id, due_date):
        return

    vn_date_display = date.fromisoformat(due_date).strftime("%d/%m/%Y")
    text = f"📅 Đến hạn hôm nay: <b>{html.escape(task['name'])}</b> ({vn_date_display})."

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
        logger.error("Failed to send D-0 to admin for task %d: %s", task_id, exc)
        return

    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    reminder_log_repo.log_sent(conn, task_id, "D-0", sent_at)
    logger.info("D-0 reminder sent: task_id=%d name=%r due=%s", task_id, task["name"], due_date)

    members = member_repo.get_all_members(conn)
    for member in members:
        try:
            sender.send_telegram_message(member["telegram_user_id"], text)
        except Exception as exc:
            logger.warning(
                "Failed to send D-0 to member %d: %s", member["telegram_user_id"], exc
            )
```

### Updated `_tick` (exact diff)

Replace the loop body and `# Story 2.3` comment:

```python
def _tick(conn, _now=None) -> None:
    """One scheduler tick. _now is injectable for testing (defaults to VN local time)."""
    logger.debug("Scheduler tick")
    if _now is None:
        _now = datetime.now(_VN_TZ)
    if _now.hour < 8:
        return
    tasks = task_repo.get_all_tasks(conn)
    tomorrow = _now.date() + timedelta(days=1)
    today = _now.date()
    for task in tasks:
        try:
            due = date.fromisoformat(task["next_due_date"])
        except (ValueError, TypeError):
            logger.warning("Task %d has invalid next_due_date: %r", task["id"], task["next_due_date"])
            continue
        if due == tomorrow:
            _check_d1(conn, task)
        if due == today:
            _check_d0(conn, task)
    # Story 2.5: add overdue check here
```

### Updated `sender.py` (exact diff)

```python
def send_telegram_message(chat_id: int, text: str, reply_markup=None) -> None:
    """Send a Telegram message from the scheduler thread.

    Creates a fresh event loop via asyncio.run() — safe to call from a sync thread.
    Reads TELEGRAM_BOT_TOKEN from env on each call (no shared Bot instance).
    Raises on Telegram API error — callers are responsible for catching.
    No imports from homekeeper.bot (AD-1).
    reply_markup: optional InlineKeyboardMarkup (passed for admin D-0 sends; None for members and D-1).
    """
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    async def _send() -> None:
        async with Bot(token) as bot:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

    asyncio.run(_send())
```

### Callback Data Format (Story 2.4 contract)

Button `callback_data` must encode both the action and the task context:
- `"done:{task_id}:{due_date}"` — e.g. `"done:42:2026-07-01"`
- `"skip:{task_id}:{due_date}"` — e.g. `"skip:42:2026-07-01"`

Story 2.4's `bot/reminder_callbacks.py` will parse this format to look up the `REMINDER_LOG` row by `(task_id, type='D-0', date=due_date)` and write `confirmed_at`. Max callback_data length is 64 bytes; the format above stays well under that limit.

### Idempotency Design for D-0

`already_sent(conn, task_id, "D-0", reminder_date)` where `reminder_date = due_date` (the due date itself).

`log_sent` stores `sent_at` as a UTC ISO-8601 datetime string. SQLite `date(sent_at)` extracts the UTC calendar date. Because the 08:00 VN gate means any send occurs at VN ≥ 08:00 = UTC ≥ 01:00, the UTC calendar date always equals the VN calendar date for sends in the valid window. So `date(sent_at)` = `due_date` reliably, and idempotency is correct. (Same reasoning validated for D-1 in Story 2.2 code review.)

### Test Catalogue for `tests/test_scheduler_d0.py`

Copy the helper functions `today_str()`, `make_vn_time()` from `tests/test_scheduler_d1.py` verbatim. The conn fixture creates an in-memory SQLite DB with the full schema (same pattern as test_scheduler_d1.py).

| # | Test name | What it verifies |
|---|-----------|------------------|
| 1 | `test_tick_before_8am_skips_d0` | `_tick(_now=make_vn_time(7, 59))` with task due today → no send |
| 2 | `test_tick_sends_d0_for_task_due_today` | `_tick(_now=make_vn_time(8, 1))` with task due `today_str()` → `send_telegram_message` called |
| 3 | `test_tick_does_not_send_d0_for_task_due_tomorrow` | task due `tomorrow_str()` → D-0 NOT called (D-1 may be called but that's separate) |
| 4 | `test_check_d0_sends_when_not_yet_sent` | clean DB, task due today → send called, REMINDER_LOG row inserted |
| 5 | `test_check_d0_admin_receives_keyboard` | assert `sender.send_telegram_message` first call's `reply_markup` is not None (is an `InlineKeyboardMarkup`) |
| 6 | `test_check_d0_members_receive_no_keyboard` | 2 members registered → member calls have `reply_markup` absent or None |
| 7 | `test_check_d0_skips_when_already_sent` | pre-insert REMINDER_LOG `type='D-0'` for today → no send |
| 8 | `test_check_d0_skips_when_task_changed` | update `next_due_date` in DB between task fetch and check → `_task_unchanged` returns False, no send, no log |
| 9 | `test_check_d0_no_log_on_admin_send_failure` | mock sender raises → no REMINDER_LOG row |
| 10 | `test_check_d0_continues_on_member_failure` | member 1 send raises, member 2 still attempted |
| 11 | `test_check_d0_sends_to_admin_and_all_members` | 2 members → 3 total `send_telegram_message` calls |
| 12 | `test_check_d0_callback_data_contains_task_id_and_due_date` | assert button callback_data strings are `f"done:{task_id}:{due_date}"` and `f"skip:{task_id}:{due_date}"` |

**Test 5 / 6 tip** — to assert on the keyboard argument, capture calls:

```python
with patch("homekeeper.scheduler.sender.send_telegram_message") as mock_send:
    _check_d0(conn, task)
calls = mock_send.call_args_list
admin_call = calls[0]
reply_markup_arg = admin_call.kwargs.get("reply_markup") or admin_call.args[2] if len(admin_call.args) > 2 else None
assert reply_markup_arg is not None
# member calls
for call in calls[1:]:
    member_markup = call.kwargs.get("reply_markup")
    assert member_markup is None
```

**Test 12 tip** — inspect button callback_data from the keyboard:

```python
from telegram import InlineKeyboardMarkup
# reply_markup_arg obtained above
assert isinstance(reply_markup_arg, InlineKeyboardMarkup)
buttons = reply_markup_arg.inline_keyboard[0]
assert buttons[0].callback_data == f"done:{task_id}:{today_str()}"
assert buttons[1].callback_data == f"skip:{task_id}:{today_str()}"
```

### File Map

| File | Action | Notes |
|------|--------|-------|
| `homekeeper/scheduler/sender.py` | UPDATE | Add `reply_markup=None` param; pass to `bot.send_message` |
| `homekeeper/scheduler/loop.py` | UPDATE | Add `from telegram import InlineKeyboardButton, InlineKeyboardMarkup`; add `_check_d0`; update `_tick` |
| `tests/test_sender.py` | UPDATE | Update existing assertion to include `reply_markup=None`; add 2 new tests |
| `tests/test_scheduler_d0.py` | NEW | 12 tests (see Test Catalogue) |

### Project Structure Notes

- `from telegram import InlineKeyboardButton, InlineKeyboardMarkup` belongs in `loop.py` at module level alongside the other imports (after stdlib, before homekeeper imports). This is AD-1 compliant — `telegram` is a third-party library, not `homekeeper.bot`.
- `tests/test_scheduler_d0.py` follows the exact same DB fixture pattern as `tests/test_scheduler_d1.py`. Copy the `conn` fixture and helper functions unchanged.
- Member rows in test DB: `INSERT INTO MEMBER (telegram_user_id, name) VALUES (?, ?)`. The `get_all_members` function returns sqlite3 Row objects accessed by `member["telegram_user_id"]`.

### References

- Epics spec: AC-1, AC-2, AC-3 for Story 2.3 — `_bmad-output/planning-artifacts/epics.md`
- Architecture constraints AD-1, AD-2, AD-5, AD-8 — `_bmad-output/planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md`
- `_check_d1` mirror pattern — `homekeeper/scheduler/loop.py:29-69`
- `already_sent` / `log_sent` — `homekeeper/db/reminder_log_repo.py`
- `get_all_members` — `homekeeper/db/member_repo.py`
- Schema (REMINDER_LOG, TASK, MEMBER) — `homekeeper/db/schema.sql`
- Story 2.2 (D-1 implementation) — `_bmad-output/implementation-artifacts/2-2-d-1-reminder-delivery.md`
- Story 2.4 (callback handler, owns `bot/reminder_callbacks.py`) — Story 2.4 will parse `done:{task_id}:{due_date}` / `skip:{task_id}:{due_date}` callback_data

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- RED/GREEN cycle: test_tick_sends_d0_for_task_due_today correctly failed until Task 3 wired `_tick` — confirmed TDD sequence correct.

### Completion Notes List

- Task 1: `sender.py` extended with backward-compatible `reply_markup=None` parameter. Updated 1 existing test assertion + added 2 new sender tests. All 5 tests pass.
- Task 2: `_check_d0` implemented in `loop.py` mirroring `_check_d1` pattern. Admin gets `InlineKeyboardMarkup` with `done:{task_id}:{due_date}` / `skip:{task_id}:{due_date}` callback_data. Members get text-only (FR-8). 12 new tests all pass.
- Task 3: `_tick` updated with `today = _now.date()` and `if due == today: _check_d0(conn, task)`. Placeholder comment removed.
- Task 4: Full 111-test suite passes with zero regressions.

### File List

- `homekeeper/scheduler/sender.py` — UPDATED (added `reply_markup=None` param)
- `homekeeper/scheduler/loop.py` — UPDATED (added InlineKeyboard imports, `_check_d0` function, `_tick` D-0 branch)
- `tests/test_sender.py` — UPDATED (1 assertion updated + 2 new tests)
- `tests/test_scheduler_d0.py` — NEW (12 tests for D-0 logic)

### Change Log

- 2026-06-30: Story 2.3 implemented — D-0 reminder with inline keyboard for Admin, text-only for Members. 12 new tests, 2 new sender tests, 111 total passing.
