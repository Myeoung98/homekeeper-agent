# Story 1.1: Bot Foundation & Admin Auth

---
baseline_commit: NO_VCS
---

Status: done

## Story

As a Admin,
I want a running Telegram bot that recognizes me as the authorized admin,
so that I can securely manage my home maintenance tasks without others interfering.

## Acceptance Criteria

1. **[AC-1] Startup & DB init:** Given `ADMIN_USER_ID` and `DB_PATH` set in `.env`, when Admin runs `python main.py`, then bot starts, connects to Telegram, `db/schema.sql` runs to create all 5 tables (TASK, MEMBER, REPAIRMAN, REMINDER_LOG, INCIDENT) if not exist with `PRAGMA journal_mode=WAL`, and logs "HomeKeeper Agent started" to console.

2. **[AC-2] Admin pass:** Given Admin sends any command, when Telegram user ID matches `ADMIN_USER_ID`, then bot processes and responds normally.

3. **[AC-3] Non-admin reject:** Given a different user sends any command, when Telegram user ID does not match `ADMIN_USER_ID`, then bot replies "Bạn không có quyền sử dụng bot này." and takes no action.

4. **[AC-4] Missing env fail-fast:** Given `ADMIN_USER_ID` or `DB_PATH` not set in `.env`, when bot starts, then it logs a clear error and exits — never starts with incomplete config.

## Tasks / Subtasks

- [x] Task 1 — Project scaffold (AC: 1, 4)
  - [x] Create directory tree: `homekeeper/bot/`, `homekeeper/scheduler/`, `homekeeper/db/`, `homekeeper/domain/` — each with `__init__.py`
  - [x] Create `requirements.txt` with exact minimum versions: `python-telegram-bot>=21.0`, `python-dotenv>=1.0`
  - [x] Create `.env.example` with `ADMIN_USER_ID=`, `DB_PATH=homekeeper.db`, `TELEGRAM_BOT_TOKEN=`
  - [x] Create `.gitignore` including `.env` and `*.db`

- [x] Task 2 — Database foundation (AC: 1)
  - [x] Create `homekeeper/db/schema.sql` with all 5 `CREATE TABLE IF NOT EXISTS` statements
  - [x] Create `homekeeper/db/connection.py` with `open_db() -> sqlite3.Connection`: opens `DB_PATH`, executes `PRAGMA journal_mode=WAL`, runs `schema.sql` (idempotent), sets `conn.row_factory = sqlite3.Row`, returns connection

- [x] Task 3 — Bot skeleton + Admin auth (AC: 1, 2, 3, 4)
  - [x] Create `homekeeper/bot/__init__.py` with `admin_only` decorator
  - [x] Create `main.py`: load `.env` via `python-dotenv` (first line), validate ADMIN_USER_ID + DB_PATH + TELEGRAM_BOT_TOKEN (fail-fast with `sys.exit(1)` if any missing), call `open_db()`, build PTB Application, add `/start` handler, log "HomeKeeper Agent started", call `application.run_polling()`
  - [x] Scheduler thread wiring: `# TODO Story 2.1: start scheduler thread here` in `main.py`

- [x] Task 4 — Manual smoke test (AC: 2, 3, 4)
  - [x] Syntax verified (ast.parse) for all 4 Python files — all pass
  - [x] Schema verified: all 5 tables present, no PRAGMA in schema.sql
  - [x] connection.py: WAL pragma, row_factory, executescript, check_same_thread not bypassed (AD-5)
  - [x] admin_only: ADMIN_USER_ID check + correct rejection message
  - [x] main.py: load_dotenv first line, fail-fast on missing vars, scheduler TODO, startup log
  - [x] AD-1 verified: db/ and domain/ have zero upward imports
  - [x] AD-4 verified: no HTTP client in codebase

## Dev Notes

### Stack & Versions

- **Python:** ≥ 3.12 — use modern type hints (`str | None` not `Optional[str]`)
- **python-telegram-bot:** ≥ 21.0 — PTB v20+ is fully async; all handlers are `async def`; use `ApplicationBuilder` pattern (not `Updater`)
- **python-dotenv:** ≥ 1.0 — call `load_dotenv()` at the very top of `main.py` before any `os.environ` access
- **SQLite:** bundled with Python — no extra install needed

### PTB v21 Startup Pattern (critical — v20 API is incompatible)

```python
# main.py
from dotenv import load_dotenv
load_dotenv()  # MUST be before os.environ access

import logging, os, sys
from telegram.ext import ApplicationBuilder, CommandHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    admin_id = os.environ.get("ADMIN_USER_ID")
    db_path  = os.environ.get("DB_PATH")
    if not admin_id or not db_path:
        logger.error("ADMIN_USER_ID and DB_PATH must be set in .env")
        sys.exit(1)

    from homekeeper.db.connection import open_db
    open_db()  # initialises schema + WAL on startup

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN must be set in .env")
        sys.exit(1)

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start_handler))
    # TODO Story 2.1: start scheduler thread here

    logger.info("HomeKeeper Agent started")
    application.run_polling()

if __name__ == "__main__":
    main()
```

Add `TELEGRAM_BOT_TOKEN=` to `.env.example` — bot needs it.

### Admin Auth Decorator (must be reused by ALL handlers in every epic)

```python
# homekeeper/bot/__init__.py
import os
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def admin_only(func):
    """Rejects non-admin callers before the handler runs."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        admin_id = int(os.environ["ADMIN_USER_ID"])
        if update.effective_user.id != admin_id:
            await update.effective_message.reply_text(
                "Bạn không có quyền sử dụng bot này."
            )
            return
        return await func(update, context)
    return wrapper
```

Apply as `@admin_only` on every `CommandHandler` callback and every `ConversationHandler` entry-point in all future stories.

### DB Schema — all 5 tables in `homekeeper/db/schema.sql`

```sql
CREATE TABLE IF NOT EXISTS TASK (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    cycle_days   INTEGER NOT NULL,
    next_due_date TEXT   NOT NULL,  -- ISO-8601 date string YYYY-MM-DD (always UTC internally)
    created_at   TEXT    NOT NULL   -- ISO-8601 datetime
);

CREATE TABLE IF NOT EXISTS MEMBER (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL UNIQUE,
    name             TEXT
);

CREATE TABLE IF NOT EXISTS REPAIRMAN (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    phone        TEXT NOT NULL,
    service_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS REMINDER_LOG (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES TASK(id),
    type         TEXT    NOT NULL,  -- 'D-1' | 'D-0' | 'overdue' | 'catchup'
    sent_at      TEXT    NOT NULL,  -- ISO-8601 datetime
    confirmed_at TEXT               -- NULL until Admin taps ✅ or ⏭
);

CREATE TABLE IF NOT EXISTS INCIDENT (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reported_by INTEGER NOT NULL,   -- Telegram user ID (Admin or Member)
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
```

### DB Connection Pattern — one connection per thread (AD-5)

```python
# homekeeper/db/connection.py
import os, sqlite3
from pathlib import Path

def open_db() -> sqlite3.Connection:
    """Open a new SQLite connection for the calling thread. Call once per thread."""
    db_path = os.environ["DB_PATH"]
    conn = sqlite3.connect(db_path)          # default check_same_thread=True is CORRECT
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent / "schema.sql"
    conn.executescript(schema.read_text())
    conn.commit()
    return conn
```

`check_same_thread=True` (default) is intentional — it enforces AD-5 that connections are never passed across threads. Each thread must call `open_db()` itself.

### Architecture Constraints to Enforce (AD-1 through AD-8)

| Rule | What it means for this story |
|------|------------------------------|
| AD-1 Downward-only imports | `bot/` may import `db/` and `domain/`. `db/` and `domain/` must NEVER import from `bot/` or `scheduler/`. |
| AD-2 No shared state | Bot thread and scheduler thread share nothing in memory — only SQLite. Never pass a connection across threads. |
| AD-3 Domain pure Python | `homekeeper/domain/` imports only stdlib. No `telegram`, `sqlite3`, third-party in domain files. |
| AD-5 WAL + one conn/thread | `PRAGMA journal_mode=WAL` on every new connection. `check_same_thread=True` (default). |
| AD-8 Single writer | Only `bot/reminder_callbacks.py` writes `TASK.next_due_date` — enforced starting Story 2.4. |

### Dates & Times Convention

- All dates stored as `TEXT` in ISO-8601 format: `YYYY-MM-DD` for dates, `YYYY-MM-DDTHH:MM:SS` for datetimes
- Always store in UTC internally
- Convert to Vietnam time (UTC+7) only at display time (`datetime + timedelta(hours=7)`)
- Use Python `datetime.date.today()` / `datetime.datetime.utcnow()` — never `time.time()`

### File List for This Story (all NEW)

```
main.py
requirements.txt
.env.example
.gitignore
homekeeper/__init__.py
homekeeper/bot/__init__.py          ← admin_only decorator lives here
homekeeper/scheduler/__init__.py
homekeeper/db/__init__.py
homekeeper/db/schema.sql            ← all 5 CREATE TABLE IF NOT EXISTS
homekeeper/db/connection.py         ← open_db()
homekeeper/domain/__init__.py
```

No existing files are modified — this is the first story.

### Project Structure Notes

- Root of project is `/Users/ton/Code/Claude/Vibe/` but the bot code lives inside `homekeeper/` package.
- `main.py` sits at the project root (alongside `requirements.txt`, `.env`)
- Do NOT create `tests/` folder in this story — test infrastructure is deferred post-v1 per Architecture "Deferred" section
- Do NOT create `homekeeper/bot/task_handlers.py` or other handler files — they belong to later stories

### References

- [Source: planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md — Structural Seed]
- [Source: planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md — AD-1 through AD-8]
- [Source: planning-artifacts/architecture/architecture-Vibe-2026-06-24/ARCHITECTURE-SPINE.md — Consistency Conventions]
- [Source: planning-artifacts/epics.md — Story 1.1 Acceptance Criteria]
- [Source: planning-artifacts/prds/prd-Vibe-2026-06-23/prd.md — FR-12]

### Review Findings

- [x] [Review][Patch] admin_only: parse ADMIN_USER_ID safely — add try/except ValueError + None-guard; read per-call but with explicit error handling [homekeeper/bot/__init__.py:8]
- [x] [Review][Patch] admin_only: guard `update.effective_user is None` before `.id` access — AttributeError on channel posts [homekeeper/bot/__init__.py:9]
- [x] [Review][Patch] admin_only: guard `update.effective_message is None` in rejection reply — AttributeError on callback queries without message [homekeeper/bot/__init__.py:11]
- [x] [Review][Patch] start_handler: replace `update.message.reply_text` with `update.effective_message.reply_text` — consistent with admin_only pattern [main.py:24]
- [x] [Review][Patch] open_db(): add `PRAGMA foreign_keys = ON` — FK constraints in schema.sql are silently unenforced without it [homekeeper/db/connection.py]
- [x] [Review][Patch] main(): wrap `open_db()` in try/except with `logger.error + sys.exit(1)` — unhandled OperationalError or FileNotFoundError gives confusing traceback [main.py:43]
- [x] [Review][Patch] connection.py: auto-create DB_PATH parent directory — `Path(db_path).parent.mkdir(parents=True, exist_ok=True)` before connect [homekeeper/db/connection.py:7]
- [x] [Review][Defer] WAL pragma return value not checked — silent fallback on network fs; personal bot runs on local disk, not a realistic risk [homekeeper/db/connection.py:9] — deferred, pre-existing
- [x] [Review][Defer] conn.commit() after executescript() is a no-op — harmless for DDL-only schema; becomes relevant if migrations added later [homekeeper/db/connection.py:14] — deferred, pre-existing
- [x] [Review][Defer] schema.sql re-read from disk on every open_db() call — low impact for personal bot (called once per thread) — deferred, pre-existing
- [x] [Review][Defer] REPAIRMAN.phone no UNIQUE constraint — consistent with v1 manual-entry UX; Story 3.1 owns this table — deferred, pre-existing

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Syntax validation: all 4 Python files parse cleanly (ast.parse)
- Schema validation: all 5 tables present, PRAGMA correctly in connection.py not schema.sql
- Architecture constraint validation: AD-1 (no upward imports), AD-4 (no HTTP client), AD-5 (check_same_thread not bypassed) — all pass

### Completion Notes List

- load_dotenv() placed as first statement in main.py (before any os.environ access) — critical for dotenv to work
- TELEGRAM_BOT_TOKEN added to .env.example and validated at startup (not in original story spec but required for bot to connect)
- check_same_thread=True (SQLite default) intentionally preserved — enforces AD-5 that connections are never shared across threads
- open_db() called in main thread at startup for schema init; scheduler thread (Story 2.1) and PTB thread each call open_db() independently
- admin_only decorator uses update.effective_message.reply_text (works for both messages and callback queries, not just update.message)
- No test framework created — Architecture explicitly defers test infrastructure post-v1; Task 4 smoke test done via static analysis and AC verification scripts

### File List

- main.py (NEW)
- requirements.txt (NEW)
- .env.example (NEW)
- .gitignore (NEW)
- homekeeper/__init__.py (NEW)
- homekeeper/bot/__init__.py (NEW)
- homekeeper/scheduler/__init__.py (NEW)
- homekeeper/db/__init__.py (NEW)
- homekeeper/db/schema.sql (NEW)
- homekeeper/db/connection.py (NEW)
- homekeeper/domain/__init__.py (NEW)
