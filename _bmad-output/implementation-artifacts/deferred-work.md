# Deferred Work

## Deferred from: code review of 1-3-view-task-list (2026-06-28)

- Message length overflow / pagination: `/list` will hit Telegram's 4096-char limit at ~16 worst-case (200-char names) or ~60 typical tasks. Pagination or truncation with "… and N more" needed. Explicitly deferred in Story 1.3 design.
- `@admin_only` missing on ConversationHandler state callbacks (`receive_name`, `receive_cycle`, `receive_date`, `cancel`): pre-existing from Story 1.2. `/cancel` is a CommandHandler reachable by any user without auth. Low real-world risk since bot is private.
- Scheduler thread DB connection: when Story 2.1 adds the scheduler thread, it must call `open_db()` independently. Sharing `bot_data["db"]` across threads will raise `ProgrammingError` (SQLite `check_same_thread=True` default).
- Test gaps: no tests for corrupt `next_due_date` (e.g., datetime string `"2026-07-01T00:00:00"` passed to `date.fromisoformat`), no test for message overflow, no test for `reply_text` raising `TelegramError`.

## Deferred from: code review of 2-2-d-1-reminder-delivery (2026-06-29)

- D1 — AC-4 guard positioned before send, not immediately before `log_sent` [loop.py]: current placement prevents sending stale text; moving after send would create send-without-log gap on task mutation mid-tick.
- D2 — `asyncio.run()` raises if called from within a running event loop [sender.py]: safe in current sync daemon thread; revisit if scheduler ever moves to async.
- D3 — No `UNIQUE(task_id, type, date(sent_at))` constraint on REMINDER_LOG [schema.sql]: single-threaded today; add when multi-instance support is needed.
- D4 — Members skipped on retry when log is written before member sends complete [loop.py]: spec-intentional per AC-3 (REMINDER_LOG write must not be blocked by member sends); per-member delivery retry would require a new story.
- D5 — Bot creates a new HTTPS session per recipient [sender.py]: acceptable latency at household scale (1–5 members); optimize with connection pooling if send volume grows.
- D6 — Task name TOCTOU: stale name in message if task renamed between `get_all_tasks` and `_task_unchanged` [loop.py]: spec AC-4 only guards `next_due_date`; name staleness is cosmetic and acceptable.
- D7 — No scheduler shutdown event [loop.py]: pre-existing from Story 2.1; daemon thread sufficient for current single-process use.
- D8 — `_task_unchanged` returns `False` on deleted task with no diagnostic log [loop.py]: deleted tasks disappear from future ticks so no duplicate send occurs; add log line when debugging scheduler behavior becomes necessary.

## Deferred from: code review of 1-4-edit-and-delete-task (2026-06-29)

- `update_task`/`delete_task` silent no-op on missing task_id: `cursor.rowcount` unchecked; success message shown even if task was deleted between list display and confirm. TOCTOU race extremely low probability on single-admin personal bot.
- TOCTOU: task list index snapshot can diverge from DB state during multi-step edit/delete. Re-fetch by ID already mitigates the worst case; architectural limitation of ConversationHandler pattern.
- Code duplication: 30+ lines of task list rendering logic copy-pasted between `edit_start` and `delete_start`. Extract `_build_task_list_message(rows, header)` helper in a future cleanup pass.
- Date bound validation: `receive_edit_date` accepts any parseable DD/MM/YYYY including year 9999 or past dates. Spec does not require bounds; add if scheduler logic ever depends on sane date ranges.
- Hard-coded reminder display: confirmation message shows "nhắc trước 1 ngày vào DD/MM/YYYY" regardless of actual scheduler config. Story 2.1 owns reminder logic; update display when that story lands.
- Large cycle values: no upper bound on cycle_days (e.g., 9999999 accepted). Cosmetic only for personal bot.
- `allow_reentry=True` not set: issuing `/edit` during an active edit conversation silently re-enters the same state without restarting. Add `allow_reentry=True` when multi-session or concurrent use becomes relevant.
- `context.user_data` stale keys: edit/delete keys accumulate after END and are never cleared. Pre-existing pattern from Story 1.2; no functional risk for single-user bot.

## Deferred from: code review of 2-3-d-0-reminder-with-action-buttons (2026-07-01)

- Admin double delivery if `ADMIN_USER_ID` is also registered as a MEMBER: `_check_d0` sends admin the keyboard message, then sends them a plain text message again via the member loop. Pre-existing in `_check_d1`. Fix: exclude `ADMIN_USER_ID` from member fan-out loop when relevant.
- `ADMIN_USER_ID` env var KeyError/ValueError aborts entire `_tick` loop: `int(os.environ["ADMIN_USER_ID"])` is outside the per-task try/except in both `_check_d0` and `_check_d1`. A misconfigured env var kills all task processing that tick. Pre-existing.
- `TELEGRAM_BOT_TOKEN` KeyError propagates from `sender.py`: `os.environ["TELEGRAM_BOT_TOKEN"]` raises bare `KeyError` if missing; callers catch `Exception` but only inside the Telegram send, not the token read. Pre-existing since Story 2.2.
- REMINDER_LOG written before member fan-out completes: log row exists even if member sends never ran (e.g., process crash mid-loop). By design per AC-3 (single writer, members best-effort). Pre-existing from Story 2.2 D4.
- `Bot.__aenter__` issues extra `getMe` API call per send: `async with Bot(token) as bot:` calls `bot.initialize()` on enter, doubling API calls per message. Pre-existing from Story 2.2 D5.
- Stale keyboard buttons remain active after task cycle advances: D-0 message buttons stay live in Telegram after Admin taps "Done" and `next_due_date` advances. Story 2.4's callback handler MUST validate the `due_date` encoded in `callback_data` (`done:{task_id}:{due_date}`) against the REMINDER_LOG row to reject stale presses.
- SQLite `date(sent_at)` fragile to future `sent_at` format drift: if `sent_at` is ever stored in local time instead of UTC, `date(sent_at)` would silently produce a wrong calendar date in the VN 17:00–23:59 window. Current code is correct; risk is from future format change.
- Scheduler down on D-0 day silently drops the reminder: if scheduler is offline all day, the task's D-0 fires are never sent and there is no catch-up signal. Story 2.5 (catch-up on restart) should handle missed D-0 sends in addition to overdue tasks.

## Deferred from: code review of 2-4-task-completion-and-auto-reschedule (2026-07-01)

- D1 — No atomicity between `confirm_reminder` and `advance_next_due_date` [reminder_callbacks.py:58-64]: if the process crashes between the two writes, REMINDER_LOG is confirmed but TASK.next_due_date is not advanced. Acknowledged in Dev Notes as acceptable for household bot; add a compensating read-and-repair if stronger guarantees are needed.
- D2 — TOCTOU double-advance on two simultaneous taps [reminder_callbacks.py:46-64]: two concurrent button presses could both pass the stale-check before either write lands. PTB processes updates sequentially by default, which prevents this in practice; revisit if PTB concurrency mode is ever enabled.
- D3 — `confirmed_at` uses `strftime("%Y-%m-%dT%H:%M:%SZ")` hardcoded `Z` suffix [reminder_callbacks.py:54]: `%Z` would emit the platform's TZ abbreviation; the `Z` here is a literal character. Consistent with pre-existing pattern throughout codebase (`sender.py`, `log_sent`).
- D4 — `ADMIN_USER_ID=""` logs "not a valid integer" instead of "not configured" [reminder_callbacks.py:27-32]: misleading diagnostic; `int("")` raises `ValueError` with no guidance that the env var is simply missing. Pre-existing inconsistency with `admin_only` decorator.
- D5 — `confirm_reminder rowcount=0` case untested [reminder_callbacks.py:58-63]: when no REMINDER_LOG row matches, advance still runs and a warning is logged; this branch is intentionally untested per Dev Notes.
- D6 — `task_handlers.py update_task()` also writes `TASK.next_due_date`, violating AD-8 single-writer rule: pre-existing from Stories 1.2/1.4; out-of-scope for Story 2.4. Address in a future refactor story.
- D7 — `query.data` could be `None` causing `split()` AttributeError [reminder_callbacks.py:38-39]: PTB routes to this handler only when `callback_data` matches the registered pattern, so `None` cannot reach the handler in production; guard is unnecessary given current architecture.

## Deferred from: code review of 2-5-overdue-hourly-re-notification-and-catch-up-on-restart (2026-07-01)

- D1 — `confirmed_at` guard from AC-1 Given not implemented (`_check_overdue` relies only on 1-hour gate, not confirmed_at absence): Dev Notes explicitly say advance mechanism (AC-2) is sufficient; confirmed_at check would be redundant in the normal path.
- D2 — `confirm_reminder` silently updates multiple rows if same type+date sent twice [reminder_log_repo.py:confirm_reminder]: pre-existing, no UNIQUE constraint on (task_id, type, date(sent_at)); Story 2.2 D3 tracks this.
- D3 — `_run_loop` holds one DB connection forever with no reconnect on dead connection [loop.py:_run_loop]: pre-existing pattern from Story 2.1; daemon thread restart on connection failure is future work.
- D4 — Read-check-send-log sequence in `_check_overdue` has no transaction guard [loop.py:120-167]: pre-existing pattern consistent with `_check_d0`/`_check_d1`; single-threaded scheduler makes race extremely unlikely.
- D5 — `hours_overdue` is dead code and task 2.3 description ("hours since 08:00") contradicts spec code snippet (`days * 24`) [overdue.py:15-17]: function never called; keep for potential future display use; fix description if function is ever used.
- D6 — `any_sent_on_date` uses SQLite `date(sent_at)` in UTC, can miss sends near midnight if sent_at is stored in VN timezone [reminder_log_repo.py:51]: root cause addressed by P2 (overdue.py timezone fix); storing sent_date as separate VN-TZ column is deeper future work.
- D7 — `run_catchup` fires catch-up on every restart for multi-day-overdue tasks (spec-compliant: `any_sent_on_date` checks due_date, not recent sends) [catchup.py:29]: spec-defined behavior; may be noisy if task is overdue for many days and bot restarts frequently; consider blocking by recent overdue rows in future.

## Deferred from: code review of 3-1-repairman-directory-management (2026-07-02)

- Unicode NFD/NFC normalization for "có" confirmation [repairman_handlers.py:324]: Vietnamese keyboards on iOS/Android sometimes produce NFD sequences; `"có".lower()` != `"có"` (NFC); low risk in single-admin controlled environment; normalize with `unicodedata.normalize("NFC", text)` if users report confirmation failures.
- No rowcount check after UPDATE/DELETE [repairman_repo.py:40,47]: `update_repairman`/`delete_repairman` show success even if 0 rows affected; TOCTOU race extremely unlikely in single-admin single-thread bot; check `cursor.rowcount` and raise or return sentinel if needed.
- Error message "1 đến 0" when repairman_ids is empty in select handlers [repairman_handlers.py:162,284]: nonsensical range shown if user_data is cleared externally; branch on `not repairman_ids` separately and return END.
- No user_data cleanup on ConversationHandler.END: stale `repairman_ids`, `edit_repairman`, `edit_name`, `edit_phone`, `delete_repairman` keys accumulate; no functional risk after shared-key patch is applied; clear keys on END if memory footprint becomes a concern.

## Deferred from: code review of 3-2-incident-reporting (2026-07-05)

- `conn.commit()` inside `create_incident` repo layer — pre-existing codebase pattern across all repos; any future caller wanting atomic multi-step writes must be aware of this.
- TOCTOU re-auth in `receive_description` — member revocation between `/incident` entry and description submission is a gap; ConversationHandler state is per-user so risk is acceptable for household bot.
- Full `MEMBER` table scan on every `_is_authenticated` call — `get_all_members()` has no `WHERE` clause; optimize with targeted `SELECT 1 FROM MEMBER WHERE telegram_user_id = ?` when member count grows.
- Re-entering `/incident` while in `ASK_DESC` state silently resets first flow — standard in-memory ConversationHandler behavior (AD-7); add `allow_reentry=True` + user-facing notice if UX becomes an issue.
- No description length cap — Telegram allows up to 4096 chars; INCIDENT.description has no schema limit; add length guard if DB size becomes a concern.
- `cursor.lastrowid` returns `None` if future BEFORE trigger aborts INSERT — no current trigger exists; guard with `if incident_id is None` if schema triggers are ever added.

## Deferred from: code review of 3-3-repairman-suggestion-hitl (2026-07-06)

- Double-tap `BadRequest`: tapping "Có" twice in quick succession fires `edit_text` on already-edited message, raising unhandled `telegram.error.BadRequest: message is not modified`. Fix requires try/except around final `edit_text` or a PTB-level deduplication guard.
- 4096-char message limit: joined repairman result string can exceed Telegram's hard limit when many repairmen match a common keyword. Fix: truncate with "and N more" or paginate. Low probability at home-maintenance scale.
- Vietnamese word segmentation: `split()` splits on whitespace which in Vietnamese separates syllables, not words. "điều hòa" = two tokens but one compound word (air conditioner). Correct matching requires a Vietnamese word segmenter (e.g., `underthesea`). Design limitation, out of scope.
- Stopword false positives: common Vietnamese syllables like "nước", "điện" match across unrelated service types. Set-intersection approach produces false positives. Requires a stopword list or TF-IDF approach.
- No try/except around final `edit_text`: Telegram API errors (e.g., message too old, network timeout) propagate unhandled. Consistent with pre-existing callback pattern; would require a codebase-wide fix.
- Auth gap in `incident_yes_callback`: spec explicitly decided no auth check in callbacks ("keyboard only appears to authenticated users"); however unauthenticated users receiving repairman contact info via crafted callback is a real privacy concern. Needs product-level decision.

## Deferred from: code review of 4-1-member-management (2026-07-05)

- `delete_member` silent no-op when member row already gone — false "✅ deleted" confirmation shown to admin [homekeeper/db/member_repo.py:25]: consistent with `repairman_repo.delete_repairman` pattern; check `cursor.rowcount` and return sentinel if needed.
- TOCTOU in add flow: `get_member_by_telegram_id` pre-check passes but concurrent INSERT raises `IntegrityError` giving a generic error message instead of "Thành viên này đã có trong danh sách." [homekeeper/bot/member_handlers.py]: single-admin home bot, race probability negligible; handle `IntegrityError` specifically in `receive_add_name` if needed.
- `ADMIN_USER_ID=0` fallback emits no warning when env var is unset: `int(os.environ.get("ADMIN_USER_ID", "0"))` silently defaults to 0, locking all admins out with no diagnostic log [homekeeper/bot/member_handlers.py:25]: pre-existing systemic pattern across all handlers.
- `user_data` keys (`add_telegram_id`, `remove_member_ids`, `remove_member`) not cleared on ConversationHandler END [homekeeper/bot/member_handlers.py]: pre-existing systemic pattern from `repairman_handlers`; no functional risk for single-user bot; clear keys on END if memory footprint becomes a concern.
- `effective_message` None guard missing in state handler functions (`receive_add_id`, `receive_add_name`, `receive_remove_select`, `receive_remove_confirm`) [homekeeper/bot/member_handlers.py]: pre-existing systemic pattern in `repairman_handlers`; PTB guarantees non-None for text MessageHandler routes.

## Deferred from: code review of 4-2-member-aware-reminder-delivery (2026-07-05)

- `_check_d0` uses `any_sent_on_date` (type-agnostic) while `_check_d1` uses type-specific key [homekeeper/scheduler/loop.py]: a catchup or overdue log row on the same calendar day silently suppresses D-0; pre-existing asymmetry since Stories 2.2/2.3; low risk for a personal bot where scheduler rarely misfires.
- AC-4 "fresh query per send" not explicitly tested for catchup and overdue paths [tests/test_scheduler_catchup.py, tests/test_scheduler_overdue.py]: structural correctness verified by code inspection (no module-level `members` variable); no test deletes a member between admin send and member loop iteration.
- AC-5 `logger.warning` log level never asserted in member-failure tests: all four scheduler test files verify that iteration continues after failure but no test asserts `caplog.records` or equivalent; a future silent-except refactor would pass all tests.
- `test_check_overdue_sends_when_overdue` asserts `call_count == 1` with no members in fixture — vacuously proves admin-only behavior; should assert `chat_id == admin_id` explicitly [tests/test_scheduler_overdue.py:57].
