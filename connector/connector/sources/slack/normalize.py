from __future__ import annotations

import time
from typing import Any

from ...schemas import MsgKind, NormalizedMsg, Source


def event_to_normalized(event: dict[str, Any]) -> NormalizedMsg | None:
    """Map a Slack Events API `event_callback` message event to NormalizedMsg.

    {"type": "event_callback",
     "event": {"type": "message", "subtype": None,
               "ts": "1700000000.000100",
               "channel": "C123", "user": "U123", "text": "..."}}
    """
    ev = event.get("event") or {}
    if ev.get("type") != "message":
        return None
    if ev.get("subtype") in {"bot_message", "message_deleted", "channel_join"}:
        return None
    ts_str = ev.get("ts", "")
    try:
        ts = int(float(ts_str)) if ts_str else int(time.time())
    except ValueError:
        ts = int(time.time())
    return NormalizedMsg(
        source=Source.SLACK,
        source_msg_id=str(ts_str),
        thread_key=str(ev.get("channel", "") or "unknown"),
        ts=ts,
        sender_user_id=str(ev.get("user", "") or ""),
        sender_display="",
        kind=MsgKind.TEXT,
        text=ev.get("text", "") or "",
        raw={"team": event.get("team_id", "")},
    )
