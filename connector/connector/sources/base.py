from __future__ import annotations

import queue
from abc import ABC, abstractmethod

from ..schemas import NormalizedMsg


class Source(ABC):
    """Pushes NormalizedMsg into a shared queue. One Source per transport."""

    def __init__(self, inbound: "queue.Queue[NormalizedMsg]") -> None:
        self.inbound = inbound

    def emit(self, msg: NormalizedMsg) -> None:
        try:
            self.inbound.put_nowait(msg)
        except queue.Full:
            # Back-pressure: drop and log; pipeline can't keep up.
            import logging
            logging.getLogger(__name__).warning(
                "inbound queue full; dropped %s:%s", msg.source.value, msg.source_msg_id
            )

    @abstractmethod
    def start(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...
