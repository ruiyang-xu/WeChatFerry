from __future__ import annotations

import hashlib

from .llm.base import LlmCall
from .storage import dao
from .storage.db import WriteHandle


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def record(
    wh: WriteHandle,
    call: LlmCall,
    *,
    payload: str,
    window_key: str | None,
) -> None:
    dao.log_egress(
        wh,
        adapter=call.adapter,
        host=call.host,
        model=call.model,
        payload_sha256=sha256_hex(payload),
        bytes_sent=call.bytes_sent,
        bytes_received=call.bytes_received,
        window_key=window_key,
        ok=call.ok,
        error=call.error,
    )
