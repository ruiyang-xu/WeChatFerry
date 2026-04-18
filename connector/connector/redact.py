from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
    ("CN_ID", re.compile(r"\b\d{17}[0-9Xx]\b")),
    ("CN_PHONE", re.compile(r"\b1[3-9]\d{9}\b")),
    ("BANK", re.compile(r"\b\d{16,19}\b")),
]


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


@dataclass
class Redaction:
    text: str
    reverse_map: dict[str, str] = field(default_factory=dict)


class PiiRedactor:
    """Token-based PII redactor with an in-memory reverse map.

    Reverse map is never persisted and never transmitted. `rehydrate()` walks a
    Pydantic-serialized dict (or plain structure) and restores original values
    locally after LLM output is received.
    """

    def apply(self, text: str) -> Redaction:
        counters: dict[str, int] = {}
        revmap: dict[str, str] = {}

        def sub(kind: str, match: re.Match[str]) -> str:
            value = match.group(0)
            if kind == "BANK" and not _luhn_ok(value):
                return value
            counters[kind] = counters.get(kind, 0) + 1
            token = f"<<{kind}_{counters[kind]}>>"
            revmap[token] = value
            return token

        out = text
        for kind, pat in _PATTERNS:
            out = pat.sub(lambda m, k=kind: sub(k, m), out)
        return Redaction(text=out, reverse_map=revmap)

    def rehydrate(self, obj: Any, revmap: dict[str, str]) -> Any:
        if not revmap:
            return obj
        if isinstance(obj, str):
            for token, real in revmap.items():
                if token in obj:
                    obj = obj.replace(token, real)
            return obj
        if isinstance(obj, list):
            return [self.rehydrate(x, revmap) for x in obj]
        if isinstance(obj, dict):
            return {k: self.rehydrate(v, revmap) for k, v in obj.items()}
        return obj
