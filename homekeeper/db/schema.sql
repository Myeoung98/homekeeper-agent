CREATE TABLE IF NOT EXISTS TASK (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    cycle_days    INTEGER NOT NULL,
    next_due_date TEXT    NOT NULL,  -- ISO-8601 date YYYY-MM-DD (stored UTC)
    created_at    TEXT    NOT NULL   -- ISO-8601 datetime YYYY-MM-DDTHH:MM:SS (stored UTC)
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
    sent_at      TEXT    NOT NULL,  -- ISO-8601 datetime (stored UTC)
    confirmed_at TEXT               -- NULL until Admin taps Done or Skip
);

CREATE TABLE IF NOT EXISTS INCIDENT (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reported_by INTEGER NOT NULL,   -- Telegram user ID (Admin or Member)
    description TEXT    NOT NULL,
    created_at  TEXT    NOT NULL    -- ISO-8601 datetime (stored UTC)
);
