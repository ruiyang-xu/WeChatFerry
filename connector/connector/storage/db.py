from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock


_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)


class WriteHandle:
    """Serializes writes across the pipeline. Readers may use their own connections."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.lock = Lock()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, params)

    def executemany(self, sql: str, seq: list[tuple]) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.executemany(sql, seq)
