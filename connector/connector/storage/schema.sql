PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS contact (
    source           TEXT NOT NULL,
    source_user_id   TEXT NOT NULL,
    display_name     TEXT,
    remark           TEXT,
    company          TEXT,
    title            TEXT,
    role             TEXT,
    first_seen       INTEGER,
    last_seen        INTEGER,
    attrs_json       TEXT,
    PRIMARY KEY (source, source_user_id)
);

CREATE TABLE IF NOT EXISTS deal (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    counterparty_source     TEXT,
    counterparty_user_id    TEXT,
    title                   TEXT NOT NULL,
    normalized_title        TEXT NOT NULL,
    stage                   TEXT NOT NULL,
    amount                  REAL,
    currency                TEXT,
    expected_close_date     TEXT,
    confidence              REAL,
    needs_review            INTEGER NOT NULL DEFAULT 0,
    created_ts              INTEGER NOT NULL,
    updated_ts              INTEGER NOT NULL,
    source_window_key       TEXT,
    UNIQUE (counterparty_source, counterparty_user_id, normalized_title)
);

CREATE INDEX IF NOT EXISTS idx_deal_counterparty
    ON deal (counterparty_source, counterparty_user_id);

CREATE TABLE IF NOT EXISTS action_item (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_source            TEXT,
    owner_user_id           TEXT,
    description             TEXT NOT NULL,
    due_date                TEXT,
    status                  TEXT NOT NULL DEFAULT 'open',
    source_message_id       TEXT,
    confidence              REAL,
    created_ts              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_action_due
    ON action_item (due_date, status);

CREATE TABLE IF NOT EXISTS summary (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source                  TEXT NOT NULL,
    thread_key              TEXT NOT NULL,
    window_start            INTEGER NOT NULL,
    window_end              INTEGER NOT NULL,
    body_json               TEXT NOT NULL,
    created_ts              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summary_thread
    ON summary (source, thread_key, window_end DESC);

CREATE TABLE IF NOT EXISTS message_raw (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source                  TEXT NOT NULL,
    source_msg_id           TEXT NOT NULL,
    ts                      INTEGER NOT NULL,
    sender_user_id          TEXT,
    thread_key              TEXT NOT NULL,
    kind                    TEXT,
    text                    TEXT,
    raw_json                TEXT,
    ingested_ts             INTEGER NOT NULL,
    UNIQUE (source, source_msg_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_thread
    ON message_raw (source, thread_key, ts);

CREATE TABLE IF NOT EXISTS entity_link (
    entity_type             TEXT NOT NULL,
    entity_id               INTEGER NOT NULL,
    message_id              INTEGER NOT NULL,
    PRIMARY KEY (entity_type, entity_id, message_id)
);

CREATE TABLE IF NOT EXISTS egress_log (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                      INTEGER NOT NULL,
    adapter                 TEXT NOT NULL,
    host                    TEXT NOT NULL,
    model                   TEXT,
    payload_sha256          TEXT NOT NULL,
    bytes_sent              INTEGER NOT NULL,
    bytes_received          INTEGER,
    window_key              TEXT,
    ok                      INTEGER NOT NULL,
    error                   TEXT
);

CREATE INDEX IF NOT EXISTS idx_egress_ts ON egress_log (ts DESC);
