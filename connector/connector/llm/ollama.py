from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

from .base import LlmAdapter, LlmCall


class OllamaAdapter(LlmAdapter):
    name = "ollama"

    def __init__(self, endpoint: str, model: str, timeout_s: int = 60) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.host = urlparse(self.endpoint).netloc

    def extract_json(self, system: str, user: str, window_key: str) -> tuple[str, LlmCall]:
        payload = {
            "model": self.model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = f"{self.endpoint}/api/chat"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                r = httpx.post(url, json=payload, timeout=self.timeout_s)
                r.raise_for_status()
                content = r.json().get("message", {}).get("content", "")
                return content, LlmCall(
                    adapter=self.name,
                    host=self.host,
                    model=self.model,
                    bytes_sent=len(r.request.content or b""),
                    bytes_received=len(r.content or b""),
                    ok=True,
                    error=None,
                )
            except Exception as exc:
                last_exc = exc
                time.sleep(0.5 * (2 ** attempt))
        return "", LlmCall(
            adapter=self.name,
            host=self.host,
            model=self.model,
            bytes_sent=0,
            bytes_received=0,
            ok=False,
            error=str(last_exc),
        )
