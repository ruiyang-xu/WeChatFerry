from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx

from .base import LlmAdapter, LlmCall

_TOKEN_RE = re.compile(r"<<(PHONE|EMAIL|CN_ID|BANK)_\d+>>")


class ExternalLlmDeniedError(RuntimeError):
    pass


class ExternalAdapter(LlmAdapter):
    """OpenAI-compatible chat completions adapter.

    Fails closed: refuses hosts not in `allow_domains`, refuses text that
    contains any PII pattern (caller must have redacted already).
    """

    name = "external"

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key_env: str,
        allow_domains: list[str],
        require_redaction: bool = True,
        timeout_s: int = 60,
    ) -> None:
        if not endpoint:
            raise ExternalLlmDeniedError("external_llm.endpoint is empty")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.allow_domains = {d.lower() for d in allow_domains}
        self.require_redaction = require_redaction
        self.timeout_s = timeout_s
        self.host = urlparse(self.endpoint).netloc.lower()
        if self.host.split(":")[0] not in self.allow_domains and self.host not in self.allow_domains:
            raise ExternalLlmDeniedError(f"host {self.host!r} not in allow_domains {sorted(self.allow_domains)!r}")
        self.api_key = os.environ.get(api_key_env, "").strip()

    def _check_redacted(self, text: str) -> None:
        if not self.require_redaction:
            return
        # Re-apply detector; if anything survived, refuse.
        from ..redact import PiiRedactor
        redetect = PiiRedactor().apply(text)
        if redetect.reverse_map:
            raise ExternalLlmDeniedError("unredacted PII detected in payload; refusing external call")

    def extract_json(self, system: str, user: str, window_key: str) -> tuple[str, LlmCall]:
        self._check_redacted(system + "\n" + user)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        url = f"{self.endpoint}/chat/completions"
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
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
            return "", LlmCall(
                adapter=self.name,
                host=self.host,
                model=self.model,
                bytes_sent=0,
                bytes_received=0,
                ok=False,
                error=str(exc),
            )
