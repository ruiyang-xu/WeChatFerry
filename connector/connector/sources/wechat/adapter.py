from __future__ import annotations

import logging
import threading
from typing import Any

from ..base import Source as SourceBase
from .normalize import ContactNameCache, to_normalized

LOG = logging.getLogger(__name__)


class WeChatSource(SourceBase):
    """Bridges the pyauto Register/Wcf receive pipeline to the connector queue.

    The registered handler runs on pyauto's sync thread; it only does an O(1)
    enqueue so the receive loop is never blocked.
    """

    def __init__(self, inbound, host: str = "127.0.0.1", port: int = 10086) -> None:
        super().__init__(inbound)
        self.host = host
        self.port = port
        self._thread: threading.Thread | None = None
        self._receiver: Any | None = None
        self._bot: Any | None = None

    def start(self) -> None:
        # Lazy-import so the wcfauto dependency is optional at install time.
        from wcfauto import Register, Wcf, WxMsg

        self._bot = Wcf(host=self.host, port=self.port)
        receiver = Register()
        self._receiver = receiver
        cache = ContactNameCache(self._bot)
        emit = self.emit

        @receiver.message_register(isDivision=True, isGroup=True, isPyq=False)
        def _on_msg(bot: Wcf, msg: WxMsg) -> None:
            try:
                emit(to_normalized(msg, bot, cache))
            except Exception:
                LOG.exception("wechat normalize failed")

        self._thread = threading.Thread(target=receiver.run, name="wechat-source", daemon=True)
        self._thread.start()
        LOG.info("WeChat source started (wcf %s:%s)", self.host, self.port)

    def stop(self) -> None:
        if self._bot is not None and hasattr(self._bot, "disable_recv_msg"):
            try:
                self._bot.disable_recv_msg()
            except Exception:
                LOG.exception("wechat stop failed")
        self._thread = None
        self._receiver = None
        self._bot = None
