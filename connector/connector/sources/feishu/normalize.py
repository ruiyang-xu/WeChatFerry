from __future__ import annotations

import json
import time
from typing import Any

from ...schemas import MsgKind, NormalizedMsg, Source


def event_to_normalized(event: dict[str, Any]) -> NormalizedMsg | None:
    """Map a Feishu Open Platform v2 message event to NormalizedMsg.

    Expected shape:
    {
      "schema": "2.0",
      "event": {
        "message": {"message_id": "...", "create_time": "1700000000000",
                    "chat_id": "...", "chat_type": "group|p2p",
                    "message_type": "text|image|file|post|...",
                    "content": "{\"text\": \"...\"}"},
        "sender": {"sender_id": {"open_id": "..."}}
      }
    }
    """
    ev = event.get("event") or {}
    msg = ev.get("message") or {}
    if not msg:
        return None
    sender = (ev.get("sender") or {}).get("sender_id") or {}
    msg_type = msg.get("message_type", "")
    text = ""
    try:
        payload = json.loads(msg.get("content", "{}") or "{}")
        text = payload.get("text") or payload.get("title") or ""
    except Exception:
        text = msg.get("content", "") or ""
    kind = MsgKind.TEXT if msg_type == "text" else MsgKind.IMAGE if msg_type == "image" \
        else MsgKind.FILE if msg_type in {"file", "media"} else MsgKind.OTHER
    ts_ms = msg.get("create_time")
    try:
        ts = int(ts_ms) // 1000 if ts_ms else int(time.time())
    except ValueError:
        ts = int(time.time())
    return NormalizedMsg(
        source=Source.FEISHU,
        source_msg_id=str(msg.get("message_id", "")),
        thread_key=str(msg.get("chat_id", "")) or "unknown",
        ts=ts,
        sender_user_id=str(sender.get("open_id") or sender.get("user_id") or ""),
        sender_display="",
        kind=kind,
        text=text,
        raw={
            "message_type": msg_type,
            "chat_type": msg.get("chat_type", ""),
        },
    )
