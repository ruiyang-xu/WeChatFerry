from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from .schemas import NormalizedMsg, Source


@dataclass
class ConversationWindow:
    source: Source
    thread_key: str
    messages: list[NormalizedMsg] = field(default_factory=list)
    first_ts: int = 0
    last_ts: int = 0
    opened_wall: float = field(default_factory=time.monotonic)

    def append(self, msg: NormalizedMsg) -> None:
        if not self.messages:
            self.first_ts = msg.ts
        self.messages.append(msg)
        self.last_ts = msg.ts

    def participants(self) -> list[str]:
        return sorted({m.sender_user_id for m in self.messages if m.sender_user_id})

    def transcript(self) -> str:
        lines = []
        for m in self.messages:
            who = m.sender_display or m.sender_user_id
            lines.append(f"[{m.ts}] {who}: {m.text}")
        return "\n".join(lines)


class WindowStore:
    """Thread-safe store of open windows keyed by (source, thread_key)."""

    def __init__(
        self,
        max_messages: int = 30,
        idle_seconds: int = 90,
        max_wall_minutes: int = 15,
    ) -> None:
        self.max_messages = max_messages
        self.idle_seconds = idle_seconds
        self.max_wall_seconds = max_wall_minutes * 60
        self._windows: dict[tuple[str, str], ConversationWindow] = {}
        self._lock = Lock()

    @staticmethod
    def key(msg: NormalizedMsg) -> tuple[str, str]:
        return (msg.source.value, msg.thread_key)

    def append(self, msg: NormalizedMsg) -> ConversationWindow:
        k = self.key(msg)
        with self._lock:
            win = self._windows.get(k)
            if win is None:
                win = ConversationWindow(source=msg.source, thread_key=msg.thread_key)
                self._windows[k] = win
            win.append(msg)
            return win

    def due_for_flush(self, now: int | None = None, now_mono: float | None = None) -> list[ConversationWindow]:
        now = now if now is not None else int(time.time())
        now_mono = now_mono if now_mono is not None else time.monotonic()
        out: list[ConversationWindow] = []
        with self._lock:
            for k, win in list(self._windows.items()):
                if (
                    len(win.messages) >= self.max_messages
                    or (now - win.last_ts) >= self.idle_seconds
                    or (now_mono - win.opened_wall) >= self.max_wall_seconds
                ):
                    out.append(win)
                    del self._windows[k]
        return out

    def force_flush_all(self) -> list[ConversationWindow]:
        with self._lock:
            out = list(self._windows.values())
            self._windows.clear()
            return out
