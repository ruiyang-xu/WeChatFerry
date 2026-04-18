from __future__ import annotations

import json
import re
import time
from typing import Iterable

from .db import WriteHandle
from ..schemas import (
    ActionItem,
    ContactHint,
    Deal,
    NormalizedMsg,
    STAGE_ORDER,
    Summary,
)

_TITLE_STOPWORDS = {"the", "a", "an", "project", "deal", "opportunity", "plan"}


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    parts = [p for p in cleaned.split() if p and p not in _TITLE_STOPWORDS]
    return " ".join(parts)


def insert_message_raw(wh: WriteHandle, msg: NormalizedMsg) -> int:
    cur = wh.execute(
        """INSERT OR IGNORE INTO message_raw
             (source, source_msg_id, ts, sender_user_id, thread_key, kind, text, raw_json, ingested_ts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            msg.source.value,
            msg.source_msg_id,
            msg.ts,
            msg.sender_user_id,
            msg.thread_key,
            msg.kind.value,
            msg.text,
            json.dumps(msg.raw, ensure_ascii=False),
            int(time.time()),
        ),
    )
    if cur.lastrowid:
        return cur.lastrowid
    row = wh.execute(
        "SELECT id FROM message_raw WHERE source=? AND source_msg_id=?",
        (msg.source.value, msg.source_msg_id),
    ).fetchone()
    return int(row["id"]) if row else 0


def upsert_contact(wh: WriteHandle, c: ContactHint, now: int) -> None:
    if not (c.source and c.source_user_id):
        return
    wh.execute(
        """INSERT INTO contact (source, source_user_id, display_name, company, title, role,
                                first_seen, last_seen, attrs_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(source, source_user_id) DO UPDATE SET
             display_name = COALESCE(excluded.display_name, contact.display_name),
             company      = COALESCE(excluded.company,      contact.company),
             title        = COALESCE(excluded.title,        contact.title),
             role         = COALESCE(excluded.role,         contact.role),
             last_seen    = MAX(contact.last_seen, excluded.last_seen)""",
        (
            c.source.value,
            c.source_user_id,
            c.display_name,
            c.company,
            c.title,
            c.role,
            now,
            now,
            json.dumps({"notes": c.notes} if c.notes else {}, ensure_ascii=False),
        ),
    )


def upsert_deal(wh: WriteHandle, d: Deal, window_key: str, now: int) -> int:
    norm = normalize_title(d.title)
    needs_review = 1 if (d.amount is not None and d.confidence < 0.75) else 0
    existing = wh.execute(
        """SELECT id, stage, amount, confidence FROM deal
           WHERE counterparty_source IS ? AND counterparty_user_id IS ? AND normalized_title = ?""",
        (
            d.counterparty_source.value if d.counterparty_source else None,
            d.counterparty_user_id,
            norm,
        ),
    ).fetchone()
    if existing is None:
        cur = wh.execute(
            """INSERT INTO deal (counterparty_source, counterparty_user_id, title, normalized_title,
                                 stage, amount, currency, expected_close_date, confidence,
                                 needs_review, created_ts, updated_ts, source_window_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d.counterparty_source.value if d.counterparty_source else None,
                d.counterparty_user_id,
                d.title,
                norm,
                d.stage,
                d.amount,
                d.currency,
                d.expected_close_date,
                d.confidence,
                needs_review,
                now,
                now,
                window_key,
            ),
        )
        return int(cur.lastrowid)
    new_stage = d.stage
    old_stage = existing["stage"]
    if STAGE_ORDER.get(new_stage, 0) < STAGE_ORDER.get(old_stage, 0):
        if d.confidence < (existing["confidence"] or 0) + 0.2:
            new_stage = old_stage
    new_amount = existing["amount"]
    if d.amount is not None and d.confidence >= (existing["confidence"] or 0):
        new_amount = d.amount
    wh.execute(
        """UPDATE deal SET stage=?, amount=?, currency=COALESCE(?, currency),
                           expected_close_date=COALESCE(?, expected_close_date),
                           confidence=MAX(confidence, ?), needs_review=?,
                           updated_ts=?, source_window_key=? WHERE id=?""",
        (
            new_stage,
            new_amount,
            d.currency,
            d.expected_close_date,
            d.confidence,
            needs_review,
            now,
            window_key,
            existing["id"],
        ),
    )
    return int(existing["id"])


def insert_action(wh: WriteHandle, a: ActionItem, now: int) -> int:
    cur = wh.execute(
        """INSERT INTO action_item (owner_source, owner_user_id, description, due_date,
                                    status, source_message_id, confidence, created_ts)
           VALUES (?, ?, ?, ?, 'open', ?, ?, ?)""",
        (
            a.owner_source.value if a.owner_source else None,
            a.owner_user_id,
            a.description,
            a.due_date,
            a.source_message_id,
            a.confidence,
            now,
        ),
    )
    return int(cur.lastrowid)


def insert_summary(wh: WriteHandle, s: Summary, now: int) -> int:
    cur = wh.execute(
        """INSERT INTO summary (source, thread_key, window_start, window_end, body_json, created_ts)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            s.source.value,
            s.thread_key,
            s.window_start,
            s.window_end,
            s.model_dump_json(),
            now,
        ),
    )
    return int(cur.lastrowid)


def link_messages(wh: WriteHandle, entity_type: str, entity_id: int, message_ids: Iterable[int]) -> None:
    rows = [(entity_type, entity_id, mid) for mid in message_ids if mid]
    if not rows:
        return
    wh.executemany(
        "INSERT OR IGNORE INTO entity_link (entity_type, entity_id, message_id) VALUES (?, ?, ?)",
        rows,
    )


def log_egress(
    wh: WriteHandle,
    *,
    adapter: str,
    host: str,
    model: str | None,
    payload_sha256: str,
    bytes_sent: int,
    bytes_received: int | None,
    window_key: str | None,
    ok: bool,
    error: str | None,
) -> int:
    cur = wh.execute(
        """INSERT INTO egress_log (ts, adapter, host, model, payload_sha256, bytes_sent,
                                   bytes_received, window_key, ok, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            int(time.time()),
            adapter,
            host,
            model,
            payload_sha256,
            bytes_sent,
            bytes_received,
            window_key,
            1 if ok else 0,
            error,
        ),
    )
    return int(cur.lastrowid)
