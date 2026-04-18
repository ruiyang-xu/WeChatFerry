from __future__ import annotations

import time
from typing import Any

from ...schemas import MsgKind, NormalizedMsg, Source

# WeChat message type ids (from WeChatFerry rpc/pb_types.h and community docs).
_TEXT_TYPE = 1
_IMAGE_TYPE = 3
_FILE_TYPE = 49  # app/file/link; finer split handled by consumer if needed


def _kind_for(wx_type: int) -> MsgKind:
    if wx_type == _TEXT_TYPE:
        return MsgKind.TEXT
    if wx_type == _IMAGE_TYPE:
        return MsgKind.IMAGE
    if wx_type == _FILE_TYPE:
        return MsgKind.FILE
    return MsgKind.OTHER


class ContactNameCache:
    """Resolves wxid -> display name via bot.get_contact_info, cached with TTL."""

    def __init__(self, bot: Any, ttl: int = 600) -> None:
        self.bot = bot
        self.ttl = ttl
        self._cache: dict[str, tuple[str, float]] = {}

    def lookup(self, wxid: str) -> str:
        if not wxid:
            return ""
        now = time.monotonic()
        hit = self._cache.get(wxid)
        if hit and (now - hit[1]) < self.ttl:
            return hit[0]
        name = wxid
        try:
            info = self.bot.get_contact_info(wxid) if hasattr(self.bot, "get_contact_info") else None
            if info:
                # pyauto returns list[dict] or dict; handle both.
                if isinstance(info, list) and info:
                    info = info[0]
                if isinstance(info, dict):
                    name = info.get("remark") or info.get("name") or wxid
        except Exception:
            pass
        self._cache[wxid] = (name, now)
        return name


def to_normalized(msg: Any, bot: Any, cache: ContactNameCache) -> NormalizedMsg:
    """Map a pyauto WxMsg-like object to NormalizedMsg."""
    sender = getattr(msg, "sender", "") or ""
    roomid = getattr(msg, "roomid", "") or ""
    is_group = bool(getattr(msg, "is_group", False) or roomid.endswith("@chatroom"))
    thread_key = roomid if is_group else sender
    wx_type = int(getattr(msg, "type", 0) or 0)
    display = cache.lookup(sender) if sender else ""
    return NormalizedMsg(
        source=Source.WECHAT,
        source_msg_id=str(getattr(msg, "id", "") or ""),
        thread_key=thread_key or sender or "unknown",
        ts=int(getattr(msg, "ts", 0) or time.time()),
        sender_user_id=sender,
        sender_display=display,
        kind=_kind_for(wx_type),
        text=(getattr(msg, "content", "") or ""),
        raw={
            "wx_type": wx_type,
            "is_group": is_group,
            "xml": getattr(msg, "xml", "") or "",
        },
    )
