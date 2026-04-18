from __future__ import annotations

from abc import ABC, abstractmethod

from ..schemas import ExtractionResult


class Exporter(ABC):
    """Downstream dashboard adapter. v1 ships only this interface; the Secondaries
    implementation lands in v2 (HTTP push / NDJSON drop / direct DB write)."""

    name: str = "base"

    @abstractmethod
    def export(self, source: str, thread_key: str, result: ExtractionResult) -> None:
        ...


class NoopExporter(Exporter):
    name = "none"

    def export(self, source: str, thread_key: str, result: ExtractionResult) -> None:
        return None
