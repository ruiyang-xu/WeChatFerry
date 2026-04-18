from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LlmCall:
    """Input+output metadata for one LLM request. Used by audit."""
    adapter: str
    host: str
    model: str | None
    bytes_sent: int
    bytes_received: int | None
    ok: bool
    error: str | None


class LlmAdapter(ABC):
    """Returns a JSON string and a LlmCall record. Raw text is the redacted transcript."""

    name: str = "base"

    @abstractmethod
    def extract_json(self, system: str, user: str, window_key: str) -> tuple[str, LlmCall]:
        ...
