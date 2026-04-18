from __future__ import annotations

import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor

from .pipeline import Pipeline
from .schemas import NormalizedMsg
from .windowing import WindowStore, ConversationWindow

LOG = logging.getLogger(__name__)


class BatchWorker:
    """Drains NormalizedMsg from the inbound queue, appends to WindowStore,
    periodically flushes due windows into the LLM worker pool."""

    def __init__(
        self,
        inbound: "queue.Queue[NormalizedMsg]",
        store: WindowStore,
        pipeline: Pipeline,
        llm_workers: int = 2,
        tick_seconds: float = 1.0,
    ) -> None:
        self.inbound = inbound
        self.store = store
        self.pipeline = pipeline
        self.tick_seconds = tick_seconds
        self._executor = ThreadPoolExecutor(max_workers=llm_workers, thread_name_prefix="llm")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="batch-worker", daemon=True)
        self._thread.start()

    def stop(self, drain: bool = True) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if drain:
            for win in self.store.force_flush_all():
                try:
                    self.pipeline.process_window(win)
                except Exception:
                    LOG.exception("drain flush failed")
        self._executor.shutdown(wait=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                msg = self.inbound.get(timeout=self.tick_seconds)
                self.store.append(msg)
            except queue.Empty:
                pass
            for win in self.store.due_for_flush():
                self._executor.submit(self._safe_process, win)

    def _safe_process(self, win: ConversationWindow) -> None:
        try:
            self.pipeline.process_window(win)
        except Exception:
            LOG.exception("pipeline failed for window %s:%s", win.source.value, win.thread_key)
